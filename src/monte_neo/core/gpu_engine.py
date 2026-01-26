from __future__ import annotations

from typing import TYPE_CHECKING, Any

import mlx.core as mx
import numpy as np
import pandas as pd

from monte_neo.core.gpu_lazy import backtest_lazy_scenarios as run_lazy_backtest
from monte_neo.core.gpu_scenarios import normalize_signal_array, run_scenarios_backtest
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.workers import run_indicator_batch
from monte_neo.utils.parallel import ParallelExecutor

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator


class MLXBacktestEngine:
    """GPU-accelerated backtesting engine using MLX."""

    def __init__(self) -> None:
        # M1 Pro usually has enough memory to hold large matrices
        pass

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
        """Run multiple backtests simultaneously on the GPU.

        Args:
            data: OHLCV DataFrame.
            indicators: List of indicators to test.
            executor: Optional shared parallel executor for signal generation.
            use_shared_data: Whether to use shared memory for data (reduces IPC).
            force_parallel: Force multiprocessing for signal generation.
            parallel_threshold: Indicator count threshold for multiprocessing.
            dynamic_parallel_threshold: Threshold for dynamic indicators multiprocessing.
            use_sl_tp: Whether to apply Stop Loss and Take Profit.
            sl_pct: Stop Loss percentage.
            tp_pct: Take Profit percentage.

        Returns:
            List of results for each indicator.
        """
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
                    raw_signals.append(ind.generate_signals(data))
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
            return results

        # Normal GPU calculation (Simple vectorized model)
        signal_list = []
        for sigs in raw_signals:
            signal_list.append(normalize_signal_array(sigs, len(data)))

        # Shape: (N, T)
        signal_matrix = mx.array(np.stack(signal_list))

        # Shift prices for returns calculation
        returns_pct = (close_prices[1:] / close_prices[:-1]) - 1

        # Shift signals to avoid look-ahead bias
        strat_returns = signal_matrix[:, :-1] * returns_pct

        # Cumulative returns (Equity Curves)
        equity_curves = mx.exp(
            mx.cumsum(mx.log1p(mx.clip(strat_returns, -0.999, 10.0)), axis=1)
        )

        # Final Return
        final_returns = equity_curves[:, -1]

        # Max Drawdown
        running_max = mx.cummax(equity_curves, axis=1)
        max_dds = mx.max((running_max - equity_curves) / running_max, axis=1)

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

        for i in range(len(indicators)):
            res = {
                "total_return": float(final_rets_np[i]) - 1.0,
                "max_drawdown": float(max_dds_np[i]),
                "profit_factor": float(pf_np[i]),
                "metrics": {
                    "total_return": float(final_rets_np[i]) - 1.0,
                    "max_drawdown": float(max_dds_np[i]),
                    "profit_factor": float(pf_np[i]),
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
