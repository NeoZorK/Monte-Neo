from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
import mlx.core as mx
import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator
    from monte_neo.core.mlx_engine import MLXBacktestEngine
    from monte_neo.utils.parallel import ParallelExecutor

logger = logging.getLogger(__name__)

def run_full_simulation_impl(
    engine: MLXBacktestEngine,
    data: pd.DataFrame,
    indicator_or_list: Union[BaseIndicator, list[BaseIndicator]],
    n_scenarios: int,
    method: str = "shuffling",
    seed: int = 42,
    use_sl_tp: bool = False,
    sl_pct: float = 0.0,
    tp_pct: float = 0.0,
    **kwargs: Any,
) -> tuple[Union[list[dict[str, Any]], list[list[dict[str, Any]]]], dict[str, float]]:
    """Implementation of full simulation."""
    from monte_neo.core.acceleration.cpp_metal.metal_engine import Candle
    from monte_neo.metrics.calculator import MetricsCalculator

    start_total = time.perf_counter()
    timing_stats = {}
    indicators = indicator_or_list if isinstance(indicator_or_list, list) else [indicator_or_list]
    
    if engine.native_bridge and len(indicators) > 1:
        try:
            results_3d = engine.backtest_3d(
                indicators=indicators, data=data, n_scenarios=n_scenarios, use_sl_tp=use_sl_tp,
                sl_pct=sl_pct, tp_pct=tp_pct, commission_bps=kwargs.get("commission_bps", 5.0),
                slippage_bps=kwargs.get("slippage_bps", 5.0), method=method, seed=seed
            )
            timing_stats["total"] = time.perf_counter() - start_total
            return results_3d, timing_stats
        except Exception as e:
            logger.warning(f"3D Backtest failed, falling back: {e}")

    indicator = indicators[0]
    mlx_strategy = indicator.to_mlx_representation()
    
    if engine.native_bridge and method == "shuffling" and hasattr(indicator, "get_metal_params"):
        metal_params = indicator.get_metal_params(
            commission_bps=kwargs.get("commission_bps", 5.0), 
            slippage_bps=kwargs.get("slippage_bps", 5.0)
        )
        if metal_params is not None:
            try:
                t_prep_start = time.perf_counter()
                candles = [Candle(float(o), float(h), float(l), float(c), float(v))
                          for o, h, l, c, v in zip(data['open'], data['high'], data['low'], data['close'], data['volume'])]
                timing_stats["data_prep"] = time.perf_counter() - t_prep_start
                
                t_kernel_start = time.perf_counter()
                results = engine.native_bridge.run_backtest(candles, metal_params * n_scenarios, n_scenarios)
                timing_stats["kernel_execution"] = time.perf_counter() - t_kernel_start
                
                formatted_results = [{"metrics": {
                    "total_return": res.total_return, "trade_count": res.trade_count,
                    "profit_factor": res.profit_factor, "win_rate": res.win_rate,
                    "max_drawdown": res.max_drawdown, "sharpe_ratio": res.sharpe_ratio
                }} for res in results]
                timing_stats["total"] = time.perf_counter() - start_total
                return formatted_results, timing_stats
            except Exception as e:
                logger.warning(f"Native Metal bridge execution failed, falling back: {e}")

    if use_sl_tp:
        from monte_neo.core.acceleration.tensor_ops import to_tensor, TensorOps
        close = to_tensor(data)["close"]
        scenarios = TensorOps.generate_shuffle_scenarios(close, n_scenarios, seed=seed) if method == "shuffling" else \
                    TensorOps.generate_noise_scenarios(close, n_scenarios, std_dev=kwargs.get('std_dev', 0.01), seed=seed)
        
        signals = mlx_strategy.generate_signals(scenarios)
        batch_metrics = MetricsCalculator.calculate_batch_multi_price_fast(
            np.array(scenarios).astype(np.float64), np.array(scenarios).astype(np.float64),
            np.array(scenarios).astype(np.float64), np.array(signals).astype(np.int32), use_sl_tp, sl_pct, tp_pct
        )
        results = [{"metrics": {"total_return": float(batch_metrics[i, 0]), "max_drawdown": float(batch_metrics[i, 1]),
                                "profit_factor": float(batch_metrics[i, 2]), "trade_count": int(batch_metrics[i, 3])}}
                  for i in range(n_scenarios)]
        timing_stats["total"] = time.perf_counter() - start_total
        return results, timing_stats

    results = engine.pure_gpu_engine.run_simulation(data=data, mlx_strategy=mlx_strategy, n_scenarios=n_scenarios, method=method, seed=seed)
    timing_stats["total"] = time.perf_counter() - start_total
    return results, timing_stats

def backtest_batch_impl(
    engine: MLXBacktestEngine,
    data: pd.DataFrame,
    indicators: list[BaseIndicator],
    executor: ParallelExecutor | None = None,
    use_shared_data: bool = False,
    force_parallel: bool = False,
    parallel_threshold: int = 1000,
    dynamic_parallel_threshold: int = 10,
    use_sl_tp: bool = False,
    sl_pct: float = 0.0,
    tp_pct: float = 0.0,
) -> list[dict[str, Any]]:
    """Implementation of batch backtest."""
    from monte_neo.core.gpu_scenarios import normalize_signal_array
    from monte_neo.monte_carlo.workers import run_indicator_batch
    from monte_neo.metrics.calculator import MetricsCalculator

    close_prices = mx.array(data["close"].to_numpy().astype(np.float32))
    use_parallel = False
    if executor and executor.use_processes:
        has_dynamic = any(hasattr(ind, "_compile_if_needed") for ind in indicators)
        use_parallel = force_parallel or len(indicators) >= parallel_threshold or (has_dynamic and len(indicators) >= dynamic_parallel_threshold)

    if use_parallel and executor:
        task_data = None if (use_shared_data and getattr(executor, "initializer", None) is not None) else data
        tasks = [(chunk, task_data) for chunk in [indicators[i:i+max(1, len(indicators)//executor.n_workers)] for i in range(0, len(indicators), max(1, len(indicators)//executor.n_workers))]]
        raw_signals = [sig for batch in executor.map(run_indicator_batch, tasks) for sig in batch]
    else:
        raw_signals = [ind.generate_signals_fast(data) for ind in indicators]

    if use_sl_tp:
        signal_matrix = np.stack([normalize_signal_array(sigs, len(data)).astype(np.int32) for sigs in raw_signals])
        batch_metrics = MetricsCalculator.calculate_batch_fast(
            data["close"].to_numpy().astype(np.float64), data["high"].to_numpy().astype(np.float64),
            data["low"].to_numpy().astype(np.float64), signal_matrix, use_sl_tp, sl_pct, tp_pct
        )
        return [{"metrics": {"total_return": float(batch_metrics[i, 0]), "max_drawdown": float(batch_metrics[i, 1]),
                            "profit_factor": float(batch_metrics[i, 2]), "trade_count": int(batch_metrics[i, 3])},
                 "total_return": float(batch_metrics[i, 0]), "max_drawdown": float(batch_metrics[i, 1]), "profit_factor": float(batch_metrics[i, 2])}
                for i in range(len(indicators))]

    signal_matrix_mx = mx.array(np.stack([normalize_signal_array(sigs, len(data)) for sigs in raw_signals]).astype(np.int32))
    returns_pct = (close_prices[1:] / close_prices[:-1]) - 1
    strat_returns = signal_matrix_mx[:, :-1] * returns_pct
    equity_curves = mx.exp(mx.cumsum(mx.log1p(mx.clip(strat_returns, -0.999, 10.0)), axis=1))
    
    final_returns = np.array(equity_curves[:, -1])
    max_dds = np.array(mx.max((mx.cummax(equity_curves, axis=1) - equity_curves) / mx.cummax(equity_curves, axis=1), axis=1))
    trade_counts = np.array(mx.sum(mx.abs(signal_matrix_mx[:, 1:] - signal_matrix_mx[:, :-1]) > 0, axis=1) / 2)
    
    gross_profit = mx.sum(mx.where(strat_returns > 0, strat_returns, 0), axis=1)
    gross_loss = mx.abs(mx.sum(mx.where(strat_returns < 0, strat_returns, 0), axis=1))
    pf_np = np.array(mx.where(gross_loss > 0, gross_profit / gross_loss, 100.0))

    return [{"total_return": float(final_returns[i]) - 1.0, "max_drawdown": float(max_dds[i]), "profit_factor": float(pf_np[i]),
             "metrics": {"total_return": float(final_returns[i]) - 1.0, "max_drawdown": float(max_dds[i]),
                         "profit_factor": float(pf_np[i]), "trade_count": int(trade_counts[i])}}
            for i in range(len(indicators))]
