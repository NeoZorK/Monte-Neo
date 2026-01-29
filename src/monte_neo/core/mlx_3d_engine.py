from __future__ import annotations
import logging
import time
from typing import Any, Dict, Optional, TYPE_CHECKING
import mlx.core as mx
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator
    from monte_neo.core.mlx_engine import MLXBacktestEngine

logger = logging.getLogger(__name__)

def backtest_3d_impl(
    engine: MLXBacktestEngine,
    indicators: list[BaseIndicator],
    data: pd.DataFrame,
    n_scenarios: int = 1,
    use_sl_tp: bool = True,
    sl_pct: float = 0.02,
    tp_pct: float = 0.04,
    commission_bps: float = 5.0,
    slippage_bps: float = 5.0,
    method: str = "shuffling",
    seed: int | None = None,
    scenarios: mx.array | None = None
) -> list[list[dict[str, Any]]]:
    """Implementation of 3D backtest."""
    start_time = time.perf_counter()
    n_pop = len(indicators)
    n_time = len(data)
    
    from monte_neo.core.acceleration.tensor_ops import to_tensor, TensorOps
    
    # 1. Generate scenarios
    if scenarios is None:
        close_mx = engine._data_prefetch_cache.get("current_close")
        if close_mx is None:
            tensors = to_tensor(data)
            close_mx = tensors["close"]
            
        effective_seed = seed if seed is not None else int(time.time())
        if method == "shuffling":
            scenarios = TensorOps.generate_shuffle_scenarios(close_mx, n_scenarios, seed=effective_seed)
        elif method == "none":
            # Just repeat original close for n_scenarios
            scenarios = mx.repeat(close_mx[None, :], n_scenarios, axis=0)
        else:
            scenarios = TensorOps.generate_noise_scenarios(close_mx, n_scenarios, seed=effective_seed)
    
    mx.eval(scenarios)
    n_scenarios = scenarios.shape[0]
    
    # 2. Generate signals
    all_signals = []
    for ind in indicators:
        mlx_strat = ind.to_mlx_representation()
        all_signals.append(mlx_strat.generate_signals(scenarios))
        
    signal_tensor = mx.stack(all_signals)
    mx.eval(signal_tensor)
    
    # 3. Calculate metrics
    mx.eval(scenarios, signal_tensor)
    scenarios_np = np.frombuffer(memoryview(scenarios), dtype=np.float32)
    signals_np = np.frombuffer(memoryview(signal_tensor), dtype=np.int32)
    
    params_np = np.array([float(sl_pct), float(tp_pct), float(commission_bps), float(slippage_bps)], dtype=np.float32)
    
    results_flat = engine.native_bridge.calculate_metrics_fast(
        scenarios_np, scenarios_np, scenarios_np,
        signals_np, params_np,
        n_pop, n_scenarios, n_time
    )
    
    # 4. Format
    results_3d = results_flat.reshape(n_pop, n_scenarios, 6)
    formatted = []
    for i in range(n_pop):
        pop_results = []
        for j in range(n_scenarios):
            res = results_3d[i, j]
            pop_results.append({
                "metrics": {
                    "total_return": res[0], "trade_count": int(res[1]), "win_rate": res[2],
                    "max_drawdown": res[3], "profit_factor": res[4], "sharpe_ratio": res[5]
                }
            })
        formatted.append(pop_results)
        
    return formatted

def backtest_population_multi_scenario_impl(
    engine: MLXBacktestEngine,
    data: pd.DataFrame,
    population: list[BaseIndicator],
    n_scenarios: int,
    method: str = "shuffling",
    seed: int = 42,
    use_sl_tp: bool = True,
    sl_pct: float = 0.02,
    tp_pct: float = 0.04,
    return_raw: bool = False,
    **kwargs: Any,
) -> Any:
    """Implementation of population multi-scenario backtest."""
    n_pop = len(population)
    tensors = engine.get_prefeteched_tensors(kwargs.get("data_key", "current"))
    if tensors is None:
        from monte_neo.core.acceleration.tensor_ops import to_tensor
        tensors = to_tensor(data)
        
    from monte_neo.core.acceleration.tensor_ops import TensorOps
    from monte_neo.core.gpu_scenarios import normalize_signal_array
    
    close = tensors["close"]
    if method == "shuffling":
        scenarios = TensorOps.generate_shuffle_scenarios(close, n_scenarios, seed=seed)
    else:
        scenarios = TensorOps.generate_noise_scenarios(close, n_scenarios, seed=seed)
        
    def process_indicator(ind):
        mlx_strat = ind.to_mlx_representation()
        if mlx_strat:
            return mlx_strat.generate_signals(scenarios)
        sig_cpu = ind.generate_signals_fast(data)
        sig_mlx = mx.array(normalize_signal_array(sig_cpu, len(data)))
        return mx.broadcast_to(sig_mlx, (n_scenarios, len(data)))

    # Generate signals for all indicators
    t0 = time.time()
    all_signals = []
    for ind in population:
        all_signals.append(process_indicator(ind))
            
    signal_tensor = mx.stack(all_signals)
    t_gen = time.time() - t0
    
    try:
        t1 = time.time()
        mx.eval(scenarios, signal_tensor)
        t_eval = time.time() - t1
        
        # Convert to numpy - use a safer method if direct np.array fails
        t2 = time.time()
        try:
            scenarios_np = np.array(scenarios, copy=False).astype(np.float32)
            signals_np = np.array(signal_tensor, copy=False).astype(np.int32)
        except Exception as e:
            logger.warning(f"Direct MLX->NumPy conversion failed, using tolist(): {e}")
            scenarios_np = np.array(scenarios.tolist(), dtype=np.float32)
            signals_np = np.array(signal_tensor.tolist(), dtype=np.int32)
        t_conv = time.time() - t2
        
        if engine.native_bridge is not None:
            t3 = time.time()
            comm_bps = kwargs.get("commission_bps", 5.0)
            slip_bps = kwargs.get("slippage_bps", 5.0)
            params_np = np.array([sl_pct, tp_pct, comm_bps, slip_bps], dtype=np.float32)
            
            results_flat = engine.native_bridge.calculate_metrics_fast(
                scenarios_np, scenarios_np, scenarios_np,
                signals_np, params_np,
                n_pop, n_scenarios, scenarios.shape[1]
            )
            t_metal = time.time() - t3
            
            logger.debug(f"3D Performance: Gen={t_gen:.3f}s, Eval={t_eval:.3f}s, Conv={t_conv:.3f}s, Metal={t_metal:.3f}s")
            
            results_3d = results_flat.reshape(n_pop, n_scenarios, 6)
            if return_raw:
                return results_3d
            return format_results_3d(results_3d, n_pop, n_scenarios)
        else:
            raise RuntimeError("Native bridge not available")
                
    except Exception as e:
        logger.warning(f"Native 3D metrics failed, falling back: {e}")
        from monte_neo.metrics.calculator import MetricsCalculator
        flat_signals = signal_tensor.reshape(-1, signal_tensor.shape[-1])
        flat_scenarios = mx.repeat(scenarios, n_pop, axis=0) 
        batch_results = MetricsCalculator.calculate_batch_multi_price_fast(
            np.array(flat_scenarios).astype(np.float64), 
            np.array(flat_scenarios).astype(np.float64), 
            np.array(flat_scenarios).astype(np.float64), 
            np.array(flat_signals).astype(np.int32), 
            use_sl_tp, sl_pct, tp_pct
        )
        res_3d = batch_results.reshape(n_pop, n_scenarios, 6)
        if return_raw:
            return res_3d
        return format_results_3d(res_3d, n_pop, n_scenarios)

def format_results_3d(results_3d: np.ndarray, n_pop: int, n_scenarios: int) -> list:
    formatted = []
    for i in range(n_pop):
        pop_results = []
        for j in range(n_scenarios):
            res = results_3d[i, j]
            pop_results.append({
                "metrics": {
                    "total_return": res[0], "trade_count": int(res[1]), "win_rate": res[2],
                    "max_drawdown": res[3], "profit_factor": res[4], "sharpe_ratio": res[5]
                }
            })
        formatted.append(pop_results)
    return formatted
