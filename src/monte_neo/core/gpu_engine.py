from __future__ import annotations

from typing import TYPE_CHECKING, Any

import time
import mlx.core as mx
import numpy as np
import pandas as pd
import logging

from monte_neo.core.gpu_lazy import backtest_lazy_scenarios as run_lazy_backtest
from monte_neo.core.gpu_scenarios import normalize_signal_array, run_scenarios_backtest
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.workers import run_indicator_batch
from monte_neo.utils.parallel import ParallelExecutor

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator


from monte_neo.core.acceleration.engine import GpuAccelerationEngine

try:
    from monte_neo.core.acceleration.cpp_metal.metal_engine import MetalBacktestBridge, Candle, Driver
    METAL_EXTENSION_AVAILABLE = True
except ImportError:
    METAL_EXTENSION_AVAILABLE = False


class MLXBacktestEngine:
    """GPU-accelerated backtesting engine using MLX."""

    def __init__(self, precision: str = "float32", metal_driver: str = "cpp") -> None:
        """
        Initialize GPU engine with specified precision.
        
        Args:
            precision: 'float32', 'float16', 'float8_e4m3', or 'float8_e5m2'
            metal_driver: Metal driver to use ('cpp', 'objc', 'swift')
        """
        self.precision = precision
        self.metal_driver = metal_driver
        self.pure_gpu_engine = GpuAccelerationEngine(
            precision=precision,
            metal_driver=metal_driver
        )
        
        # Initialize native Metal bridge if available
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

    def _select_best_driver(self) -> str:
        """Run a micro-benchmark to select the best Metal driver."""
        if not METAL_EXTENSION_AVAILABLE:
            return "cpp"
            
        logger.info("🔍 Running micro-benchmark to select best Metal driver...")
        
        # Small test data
        candles = [Candle(100.0, 101.0, 99.0, 100.0, 1000.0) for _ in range(1000)]
        params = [14.0, 14.0, 1.5, 3.0, 2.0] * 10000
        n_scenarios = 10000
        
        best_driver = "cpp"
        min_time = float('inf')
        
        for d_name, d_enum in [("cpp", Driver.CPP), ("objc", Driver.OBJC), ("swift", Driver.SWIFT)]:
            try:
                bridge = MetalBacktestBridge(d_enum)
                if bridge.init():
                    # Warmup
                    bridge.run_backtest(candles, params, 1000)
                    
                    # Benchmark
                    start = time.perf_counter()
                    bridge.run_backtest(candles, params, n_scenarios)
                    duration = time.perf_counter() - start
                    
                    logger.debug(f"  Driver {d_name}: {duration:.6f}s")
                    if duration < min_time:
                        min_time = duration
                        best_driver = d_name
            except Exception as e:
                logger.debug(f"  Driver {d_name} failed benchmark: {e}")
                
        logger.info(f"✅ Selected best Metal driver: {best_driver} ({1.0/min_time*n_scenarios:.0f} scenarios/sec)")
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
    ) -> list[dict[str, Any]]:
        """Run full simulation (Data -> Scenarios -> Signals -> Backtest) on GPU."""
        start_time = time.perf_counter()
        
        # Extract kwargs
        std_dev = kwargs.get("std_dev", 0.01)
        
        # 1. Get MLX Strategy
        mlx_strategy = indicator.to_mlx_representation()
        if mlx_strategy is None:
            raise ValueError("Indicator does not support Pure GPU execution")
            
        # Try to use native Metal Bridge for end-to-end execution if supported
        # For now, only for RSI+ATR based indicators which match our kernel
        if self.native_bridge and method == "shuffling" and hasattr(indicator, "get_metal_params"):
            try:
                logger.info(f"Using native Metal bridge ({self.metal_driver}) for end-to-end execution")
                
                # Convert data to native Candles
                candles = [Candle(r.open, r.high, r.low, r.close, r.volume) for r in data.itertuples()]
                
                # Get strategy parameters for Metal
                # Indicator should provide a list of 5 floats for the kernel
                metal_params = indicator.get_metal_params()
                
                # Expand params for all scenarios (n_scenarios * 5)
                # In our current kernel, params are unique per scenario if needed, 
                # but for grid search/MC we often use the same params.
                full_params = metal_params * n_scenarios
                
                results = self.native_bridge.run_backtest(candles, full_params, n_scenarios)
                
                # Convert BacktestResult to dict format
                formatted_results = []
                for res in results:
                    formatted_results.append({
                        "metrics": {
                            "total_return": res.total_return,
                            "trade_count": res.trade_count,
                            "win_rate": res.win_rate,
                            "max_drawdown": res.max_drawdown
                        }
                    })
                return formatted_results
            except Exception as e:
                logger.warning(f"Native Metal bridge execution failed, falling back to MLX: {e}")

        if use_sl_tp:
            # Pure GPU engine doesn't support SL/TP path dependency yet.
            # We must use Numba batch calculation.
            
            # 1. Generate Scenarios on GPU
            from monte_neo.core.acceleration.tensor_ops import to_tensor
            tensors = to_tensor(data)
            close = tensors["close"]
            
            # Note: For now we only support shuffling/noise in this path
            if method == "shuffling":
                from monte_neo.core.acceleration.tensor_ops import TensorOps
                scenarios = TensorOps.generate_shuffle_scenarios(close, n_scenarios, seed=seed)
            else:
                from monte_neo.core.acceleration.tensor_ops import TensorOps
                scenarios = TensorOps.generate_noise_scenarios(close, n_scenarios, std_dev=std_dev, seed=seed)
                
            # 2. Generate Signals on GPU
            signals = mlx_strategy.generate_signals(scenarios)
            
            # 3. Move to CPU for SL/TP Numba calc
            scenarios_np = np.array(scenarios).astype(np.float64)
            signals_np = np.array(signals).astype(np.int32)
            
            batch_metrics = MetricsCalculator.calculate_batch_multi_price_fast(
                scenarios_np, # prices
                scenarios_np, # highs
                scenarios_np, # lows
                signals_np,
                use_sl_tp,
                sl_pct,
                tp_pct
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
            
            elapsed = time.perf_counter() - start_time
            logger.info(f"GPU Simulation (MLX + Numba) for {n_scenarios} iterations took {elapsed:.4f}s")
            return results

        # 2. Run Simulation
        results = self.pure_gpu_engine.run_simulation(
            data=data,
            mlx_strategy=mlx_strategy,
            n_scenarios=n_scenarios,
            method=method,
            seed=seed
        )
        
        elapsed = time.perf_counter() - start_time
        logger.info(f"GPU Simulation (Pure MLX) for {n_scenarios} iterations took {elapsed:.4f}s")
        return results

    def _normalize_signal_array(
        self,
        signals: Any,
        target_len: int,
    ) -> np.ndarray:
        if target_len <= 0:
            return np.zeros(0, dtype=np.float32)
        if signals is None:
            return np.zeros(target_len, dtype=np.float32)
        if isinstance(signals, pd.DataFrame):
            if "signal" in signals.columns:
                arr = signals["signal"].to_numpy()
            else:
                arr = signals.to_numpy().reshape(-1)
        elif isinstance(signals, pd.Series):
            arr = signals.to_numpy()
        else:
            arr = np.asarray(signals)
        arr = arr.astype(np.float32, copy=False).reshape(-1)
        if arr.size >= target_len:
            return arr[:target_len]
        return np.pad(arr, (0, target_len - arr.size), "constant", constant_values=0)


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
        """Run multiple backtests simultaneously on the GPU."""
        start_time = time.perf_counter()
        
        # 1. Prepare Price Data (Constant for all indicators)
        close_prices = mx.array(data["close"].to_numpy().astype(np.float32))

        # 2. Collect Signals (CPU parallelized if needed)
        use_parallel = False
        if executor and executor.use_processes:
            has_dynamic = any(hasattr(ind, "_compile_if_needed") for ind in indicators)
            use_parallel = (
                force_parallel
                or len(indicators) >= parallel_threshold
                or (has_dynamic and len(indicators) >= dynamic_parallel_threshold)
            )

        if use_parallel and executor:
            n_workers = executor.n_workers
            chunk_size = max(1, len(indicators) // n_workers)
            chunks = [
                indicators[i : i + chunk_size]
                for i in range(0, len(indicators), chunk_size)
            ]
            use_shared = use_shared_data and getattr(executor, "initializer", None) is not None
            task_data = None if use_shared else data
            tasks = [(chunk, task_data) for chunk in chunks]
            batch_results = executor.map(run_indicator_batch, tasks)
            raw_signals = []
            for batch in batch_results:
                raw_signals.extend(batch)
        else:
            raw_signals = []
            for ind in indicators:
                try:
                    raw_signals.append(ind.generate_signals_fast(data))
                except Exception:
                    raw_signals.append(None)

        # 3. Handle Backtest calculation (GPU for simple, Numba Batch for SL/TP)
        if use_sl_tp:
            # SL/TP requires path-dependent calculation
            # Use parallelized batch Numba for maximum speed on CPU

            # Prepare data arrays
            close_prices_np = data["close"].to_numpy().astype(np.float64)
            high_prices_np = data["high"].to_numpy().astype(np.float64)
            low_prices_np = data["low"].to_numpy().astype(np.float64)

            # Prepare signal matrix
            signal_list = []
            for sigs in raw_signals:
                signal_list.append(normalize_signal_array(sigs, len(data)).astype(np.int32))
            signal_matrix = np.stack(signal_list)

            # Run batch calculation
            batch_metrics = MetricsCalculator.calculate_batch_fast(
                close_prices_np,
                high_prices_np,
                low_prices_np,
                signal_matrix,
                use_sl_tp,
                sl_pct,
                tp_pct
            )

            results = []
            for i in range(len(indicators)):
                total_return = float(batch_metrics[i, 0])
                max_dd = float(batch_metrics[i, 1])
                pf = float(batch_metrics[i, 2])
                trade_count = int(batch_metrics[i, 3])

                results.append({
                    "total_return": total_return,
                    "max_drawdown": max_dd,
                    "profit_factor": pf,
                    "metrics": {
                        "total_return": total_return,
                        "max_drawdown": max_dd,
                        "profit_factor": pf,
                        "trade_count": trade_count,
                    }
                })
            
            elapsed = time.perf_counter() - start_time
            logger.info(f"GPU Batch Backtest (Numba) for {len(indicators)} indicators took {elapsed:.4f}s")
            return results

        # Normal GPU calculation (Simple vectorized model)
        signal_list = []
        for sigs in raw_signals:
            signal_list.append(normalize_signal_array(sigs, len(data)))

        # Shape: (N, T)
        signal_matrix_np = np.stack(signal_list)
        signal_matrix_mx: Any = mx.array(signal_matrix_np.astype(np.int32))

        # Shift prices for returns calculation
        returns_pct = (close_prices[1:] / close_prices[:-1]) - 1

        # Shift signals to avoid look-ahead bias
        strat_returns = signal_matrix_mx[:, :-1] * returns_pct

        # Cumulative returns (Equity Curves)
        equity_curves = mx.exp(
            mx.cumsum(mx.log1p(mx.clip(strat_returns, -0.999, 10.0)), axis=1)
        )

        # Final Return
        final_returns = equity_curves[:, -1]

        # Max Drawdown
        running_max = mx.cummax(equity_curves, axis=1)
        max_dds = mx.max((running_max - equity_curves) / running_max, axis=1)

        # Trade Count (Approximate as signal changes)
        # Shift signals to find entries/exits
        sig_diff = mx.abs(signal_matrix_mx[:, 1:] - signal_matrix_mx[:, :-1])
        # A trade is usually an entry (0->1 or 0->-1) and an exit (1->0 or -1->0)
        # or a reversal (1->-1).
        # We can approximate trade count as sum of absolute changes divided by 2
        trade_counts = mx.sum(sig_diff > 0, axis=1) / 2

        # Profit Factor
        wins = mx.where(strat_returns > 0, strat_returns, 0)
        losses = mx.where(strat_returns < 0, strat_returns, 0)
        gross_profit = mx.sum(wins, axis=1)
        gross_loss = mx.abs(mx.sum(losses, axis=1))
        profit_factor = mx.where(gross_loss > 0, gross_profit / gross_loss, 100.0)

        results = []
        final_rets_np = np.array(final_returns)
        max_dds_np = np.array(max_dds)
        pf_np = np.array(profit_factor)
        trade_counts_np = np.array(trade_counts)

        for i in range(len(indicators)):
            res = {
                "total_return": float(final_rets_np[i]) - 1.0,
                "max_drawdown": float(max_dds_np[i]),
                "profit_factor": float(pf_np[i]),
                "metrics": {
                    "total_return": float(final_rets_np[i]) - 1.0,
                    "max_drawdown": float(max_dds_np[i]),
                    "profit_factor": float(pf_np[i]),
                    "trade_count": int(trade_counts_np[i]),
                },
            }
            results.append(res)

        return results

    def backtest_scenarios(
        self,
        indicator: BaseIndicator,
        scenarios: list[pd.DataFrame],
        executor: ParallelExecutor | None = None,
        use_sl_tp: bool = False,
        sl_pct: float = 0.0,
        tp_pct: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Run one indicator across many data scenarios on GPU."""
        return run_scenarios_backtest(
            indicator,
            scenarios,
            executor,
            use_sl_tp=use_sl_tp,
            sl_pct=sl_pct,
            tp_pct=tp_pct
        )

    def backtest_lazy_scenarios(
        self,
        indicator: BaseIndicator,
        n_scenarios: int,
        executor: ParallelExecutor,
        block_size: int | None = None,
        base_seed: int = 42,
        use_sl_tp: bool = False,
        sl_pct: float = 0.0,
        tp_pct: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Run backtest with lazy scenario generation (Block Bootstrap)."""
        return run_lazy_backtest(
            indicator=indicator,
            n_scenarios=n_scenarios,
            executor=executor,
            block_size=block_size,
            base_seed=base_seed,
            use_sl_tp=use_sl_tp,
            sl_pct=sl_pct,
            tp_pct=tp_pct,
        )
