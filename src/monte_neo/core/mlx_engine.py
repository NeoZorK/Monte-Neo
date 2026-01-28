
from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import TYPE_CHECKING, Any

import mlx.core as mx
import numpy as np
import pandas as pd

from monte_neo.core.acceleration.engine import GpuAccelerationEngine
from monte_neo.core.gpu_lazy import backtest_lazy_scenarios as run_lazy_backtest
from monte_neo.core.gpu_scenarios import normalize_signal_array, run_scenarios_backtest
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.workers import run_indicator_batch
from monte_neo.utils.cache import load_cache, save_cache
from monte_neo.utils.parallel import ParallelExecutor

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator

# Try to import the Metal bridge extension
try:
    from monte_neo.core.acceleration.cpp_metal.metal_engine import Candle, Driver, MetalBacktestBridge
    METAL_EXTENSION_AVAILABLE = True
except ImportError:
    # Try to auto-compile if extension is missing
    logger.info("🛠️ Metal extension not found. Attempting auto-compilation...")
    try:
        script_path = os.path.join(os.path.dirname(__file__), "acceleration/cpp_metal/compile.sh")
        if os.path.exists(script_path):
            result = subprocess.run(["bash", script_path], capture_output=True, text=True)
            if result.returncode == 0:
                from monte_neo.core.acceleration.cpp_metal.metal_engine import Candle, Driver, MetalBacktestBridge
                METAL_EXTENSION_AVAILABLE = True
                logger.info("✅ Metal extension compiled and loaded successfully.")
            else:
                logger.warning(f"❌ Auto-compilation failed: {result.stderr}")
                METAL_EXTENSION_AVAILABLE = False
        else:
            METAL_EXTENSION_AVAILABLE = False
    except Exception as e:
        logger.warning(f"⚠️ Failed to auto-compile Metal extension: {e}")
        METAL_EXTENSION_AVAILABLE = False


class MLXBacktestEngine:
    """GPU-accelerated backtesting engine using MLX."""

    def __init__(self, precision: str = "float32", metal_driver: str = "cpp", initial_capital: float = 100000.0, leverage: float = 1.0) -> None:
        self.precision = precision
        self.metal_driver = metal_driver
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.pure_gpu_engine = GpuAccelerationEngine(
            precision=precision,
            metal_driver=metal_driver,
            initial_capital=initial_capital,
            leverage=leverage
        )
        
        self.native_bridge = None
        if METAL_EXTENSION_AVAILABLE:
            if metal_driver == "auto":
                self.metal_driver = self._select_best_driver()
            else:
                self.metal_driver = metal_driver
                
            driver_enum = Driver.CPP
            if self.metal_driver == "objc": driver_enum = Driver.OBJC
            elif self.metal_driver == "swift": driver_enum = Driver.SWIFT
            
            self.native_bridge = MetalBacktestBridge(driver_enum)
            if not self.native_bridge.init():
                logger.warning(f"Failed to initialize native Metal bridge with driver {self.metal_driver}")
                self.native_bridge = None
        else:
            if metal_driver == "auto":
                self.metal_driver = "cpp"
            else:
                self.metal_driver = metal_driver

    def _select_best_driver(self) -> str:
        """Run a micro-benchmark to select the best Metal driver."""
        if not METAL_EXTENSION_AVAILABLE:
            return "cpp"
            
        # Check cache
        cached_driver = load_cache("best_metal_driver.json")
        if cached_driver:
            logger.info(f"🚀 Using cached best Metal driver: {cached_driver}")
            return cached_driver
            
        logger.info("🔍 Running micro-benchmark to select best Metal driver...")
        candles = [Candle(100.0, 101.0, 99.0, 100.0, 1000.0) for _ in range(1000)]
        params = [14.0, 14.0, 1.5, 3.0, 2.0] * 10000
        n_scenarios = 10000
        
        best_driver = "cpp"
        min_time = float('inf')
        
        for d_name, d_enum in [("cpp", Driver.CPP), ("objc", Driver.OBJC), ("swift", Driver.SWIFT)]:
            try:
                bridge = MetalBacktestBridge(d_enum)
                if bridge.init():
                    bridge.run_backtest(candles, params, 1000)
                    start = time.perf_counter()
                    bridge.run_backtest(candles, params, n_scenarios)
                    duration = time.perf_counter() - start
                    if duration < min_time:
                        min_time = duration
                        best_driver = d_name
            except Exception as e:
                logger.debug(f"  Driver {d_name} failed benchmark: {e}")
                
        logger.info(f"✅ Selected best Metal driver: {best_driver} ({1.0/min_time*n_scenarios:.0f} scenarios/sec)")
        
        # Save to cache
        save_cache("best_metal_driver.json", best_driver)
        
        return best_driver

    def run_full_simulation(
        self,
        data: pd.DataFrame,
        indicator: BaseIndicator,
        n_scenarios: int,
        method: str = "shuffling",
        seed: int = 42,
        use_sl_tp: bool = False,
        sl_pct: float = 0.0,
        tp_pct: float = 0.0,
        **kwargs: Any,
    ) -> tuple[list[dict[str, Any]], dict[str, float]]:
        start_total = time.perf_counter()
        timing_stats = {}
        mlx_strategy = indicator.to_mlx_representation()
        
        if self.native_bridge and method == "shuffling" and hasattr(indicator, "get_metal_params"):
            comm = kwargs.get("commission_bps", 5.0)
            slip = kwargs.get("slippage_bps", 5.0)
            metal_params = indicator.get_metal_params(commission_bps=comm, slippage_bps=slip)
            if metal_params is not None:
                try:
                    t_prep_start = time.perf_counter()
                    candles = [
                        Candle(float(o), float(h), float(l), float(c), float(v))
                        for o, h, l, c, v in zip(data['open'], data['high'], data['low'], data['close'], data['volume'])
                    ]
                    full_params = metal_params * n_scenarios
                    timing_stats["data_prep"] = time.perf_counter() - t_prep_start
                    
                    t_kernel_start = time.perf_counter()
                    results = self.native_bridge.run_backtest(candles, full_params, n_scenarios)
                    timing_stats["kernel_execution"] = time.perf_counter() - t_kernel_start
                    
                    t_format_start = time.perf_counter()
                    formatted_results = []
                    for res in results:
                        formatted_results.append({
                            "metrics": {
                                "total_return": res.total_return,
                                "trade_count": res.trade_count,
                                "profit_factor": res.profit_factor,
                                "win_rate": res.win_rate,
                                "max_drawdown": res.max_drawdown,
                                "sharpe_ratio": res.sharpe_ratio
                            }
                        })
                    timing_stats["result_formatting"] = time.perf_counter() - t_format_start
                    timing_stats["total"] = time.perf_counter() - start_total
                    return formatted_results, timing_stats
                except Exception as e:
                    logger.warning(f"Native Metal bridge execution failed, falling back to MLX: {e}")

        if use_sl_tp:
            from monte_neo.core.acceleration.tensor_ops import to_tensor
            tensors = to_tensor(data)
            close = tensors["close"]
            from monte_neo.core.acceleration.tensor_ops import TensorOps
            if method == "shuffling":
                scenarios = TensorOps.generate_shuffle_scenarios(close, n_scenarios, seed=seed)
            else:
                scenarios = TensorOps.generate_noise_scenarios(close, n_scenarios, std_dev=kwargs.get('std_dev', 0.01), seed=seed)
                
            if mlx_strategy is None:
                raise ValueError("Could not create MLX strategy for indicator")
                
            signals = mlx_strategy.generate_signals(scenarios)
            scenarios_np = np.array(scenarios).astype(np.float64)
            signals_np = np.array(signals).astype(np.int32)
            
            batch_metrics = MetricsCalculator.calculate_batch_multi_price_fast(
                scenarios_np, scenarios_np, scenarios_np, signals_np, use_sl_tp, sl_pct, tp_pct
            )
            
            results = []
            for i in range(n_scenarios):
                results.append({
                    "total_return": float(batch_metrics[i, 0]),
                    "max_drawdown": float(batch_metrics[i, 1]),
                    "profit_factor": float(batch_metrics[i, 2]),
                    "metrics": {
                        "total_return": float(batch_metrics[i, 0]),
                        "max_drawdown": float(batch_metrics[i, 1]),
                        "profit_factor": float(batch_metrics[i, 2]),
                        "trade_count": int(batch_metrics[i, 3]),
                    }
                })
            timing_stats["total"] = time.perf_counter() - start_total
            return results, timing_stats

        results = self.pure_gpu_engine.run_simulation(
            data=data, mlx_strategy=mlx_strategy, n_scenarios=n_scenarios, method=method, seed=seed
        )
        timing_stats["total"] = time.perf_counter() - start_total
        return results, timing_stats

    def backtest_batch(
        self,
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
        close_prices = mx.array(data["close"].to_numpy().astype(np.float32))

        use_parallel = False
        if executor and executor.use_processes:
            has_dynamic = any(hasattr(ind, "_compile_if_needed") for ind in indicators)
            use_parallel = force_parallel or len(indicators) >= parallel_threshold or (has_dynamic and len(indicators) >= dynamic_parallel_threshold)

        if use_parallel and executor:
            n_workers = executor.n_workers
            chunk_size = max(1, len(indicators) // n_workers)
            chunks = [indicators[i : i + chunk_size] for i in range(0, len(indicators), chunk_size)]
            task_data = None if (use_shared_data and getattr(executor, "initializer", None) is not None) else data
            tasks = [(chunk, task_data) for chunk in chunks]
            batch_results = executor.map(run_indicator_batch, tasks)
            raw_signals = []
            for batch in batch_results: raw_signals.extend(batch)
        else:
            raw_signals = [ind.generate_signals_fast(data) for ind in indicators]

        if use_sl_tp:
            close_prices_np = data["close"].to_numpy().astype(np.float64)
            high_prices_np = data["high"].to_numpy().astype(np.float64)
            low_prices_np = data["low"].to_numpy().astype(np.float64)
            signal_list = [normalize_signal_array(sigs, len(data)).astype(np.int32) for sigs in raw_signals]
            signal_matrix = np.stack(signal_list)
            batch_metrics = MetricsCalculator.calculate_batch_fast(
                close_prices_np, high_prices_np, low_prices_np, signal_matrix, use_sl_tp, sl_pct, tp_pct
            )
            results = []
            for i in range(len(indicators)):
                results.append({
                    "total_return": float(batch_metrics[i, 0]),
                    "max_drawdown": float(batch_metrics[i, 1]),
                    "profit_factor": float(batch_metrics[i, 2]),
                    "metrics": {
                        "total_return": float(batch_metrics[i, 0]),
                        "max_drawdown": float(batch_metrics[i, 1]),
                        "profit_factor": float(batch_metrics[i, 2]),
                        "trade_count": int(batch_metrics[i, 3]),
                    }
                })
            return results

        signal_list = [normalize_signal_array(sigs, len(data)) for sigs in raw_signals]
        signal_matrix_mx = mx.array(np.stack(signal_list).astype(np.int32))
        returns_pct = (close_prices[1:] / close_prices[:-1]) - 1
        strat_returns = signal_matrix_mx[:, :-1] * returns_pct
        equity_curves = mx.exp(mx.cumsum(mx.log1p(mx.clip(strat_returns, -0.999, 10.0)), axis=1))
        final_returns = np.array(equity_curves[:, -1])
        running_max = mx.cummax(equity_curves, axis=1)
        max_dds = np.array(mx.max((running_max - equity_curves) / running_max, axis=1))
        sig_diff = mx.abs(signal_matrix_mx[:, 1:] - signal_matrix_mx[:, :-1])
        trade_counts = np.array(mx.sum(sig_diff > 0, axis=1) / 2)
        wins = mx.where(strat_returns > 0, strat_returns, 0)
        losses = mx.where(strat_returns < 0, strat_returns, 0)
        gross_profit = mx.sum(wins, axis=1)
        gross_loss = mx.abs(mx.sum(losses, axis=1))
        pf_np = np.array(mx.where(gross_loss > 0, gross_profit / gross_loss, 100.0))

        results = []
        for i in range(len(indicators)):
            results.append({
                "total_return": float(final_returns[i]) - 1.0,
                "max_drawdown": float(max_dds[i]),
                "profit_factor": float(pf_np[i]),
                "metrics": {
                    "total_return": float(final_returns[i]) - 1.0,
                    "max_drawdown": float(max_dds[i]),
                    "profit_factor": float(pf_np[i]),
                    "trade_count": int(trade_counts[i]),
                },
            })
        return results

    def backtest_scenarios(self, indicator: BaseIndicator, scenarios: list[pd.DataFrame], executor: ParallelExecutor | None = None,
                          use_sl_tp: bool = False, sl_pct: float = 0.0, tp_pct: float = 0.0) -> list[dict[str, Any]]:
        return run_scenarios_backtest(indicator, scenarios, executor, use_sl_tp=use_sl_tp, sl_pct=sl_pct, tp_pct=tp_pct)

    def backtest_lazy_scenarios(self, indicator: BaseIndicator, n_scenarios: int, executor: ParallelExecutor,
                               block_size: int | None = None, base_seed: int = 42, use_sl_tp: bool = False,
                               sl_pct: float = 0.0, tp_pct: float = 0.0) -> list[dict[str, Any]]:
        return run_lazy_backtest(indicator=indicator, n_scenarios=n_scenarios, executor=executor, block_size=block_size,
                                 base_seed=base_seed, use_sl_tp=use_sl_tp, sl_pct=sl_pct, tp_pct=tp_pct)
