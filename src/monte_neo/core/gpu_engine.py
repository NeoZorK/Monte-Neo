from __future__ import annotations

from typing import TYPE_CHECKING, Any

import mlx.core as mx
import numpy as np
import pandas as pd

from monte_neo.core.gpu_lazy import backtest_lazy_scenarios as run_lazy_backtest
from monte_neo.core.gpu_scenarios import normalize_signal_array, run_scenarios_backtest
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

        Returns:
            List of results for each indicator.
        """
        # 1. Prepare Price Data (Constant for all indicators)
        close_prices = mx.array(data["close"].to_numpy().astype(np.float32))

        # 2. Collect Signals into a Matrix (N_indicators x T_bars)
        # Note: Indicator signal generation is still CPU-bound or partially vectorized.
        # But we can stack the results for massive parallel equity calculation.
        signal_list = []

        # Prepare args for parallel execution
        # Each task is (indicator, data)
        # Since data is same for all, we might want to avoid pickling it N times if it's huge.
        # But for parallel execution, arguments must be pickled.
        # ParallelExecutor uses process pool, so pickling is unavoidable.

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

        # Process results
        for sigs in raw_signals:
            signal_list.append(normalize_signal_array(sigs, len(data)))

        # Shape: (N, T)
        signal_matrix = mx.array(np.stack(signal_list))

        # 3. Calculate Trades / Equity on GPU
        # Simple backtesting on GPU:
        # returns = signals[t-1] * (price[t] / price[t-1] - 1)

        # Shift prices for returns calculation
        # returns_pct = (close[1:] / close[:-1]) - 1
        returns_pct = (close_prices[1:] / close_prices[:-1]) - 1

        # Shift signals to avoid look-ahead bias (signals[t] affects return between t and t+1)
        # We align: signal[0] * returns_pct[0] (which is move from close[0] to close[1])
        strat_returns = signal_matrix[:, :-1] * returns_pct

        # Cumulative returns (Equity Curves)
        # log_returns = mx.log1p(strat_returns) # For precision, but simple cumprod is fine too
        equity_curves = mx.exp(
            mx.cumsum(mx.log1p(mx.clip(strat_returns, -0.999, 10.0)), axis=1)
        )

        # 4. Calculate Metrics on GPU
        # Final Return
        final_returns = equity_curves[:, -1]

        # Max Drawdown (Vectorized across all indicators)
        # running_max = mx.maximum.accumulate(equity_curves, axis=1) # type: ignore
        running_max = mx.cummax(equity_curves, axis=1)
        drawdowns = (running_max - equity_curves) / running_max
        max_drawdowns = mx.max(drawdowns, axis=1)

        # Profit Factor
        wins = mx.where(strat_returns > 0, strat_returns, 0)
        losses = mx.where(strat_returns < 0, strat_returns, 0)
        gross_profit = mx.sum(wins, axis=1)
        gross_loss = mx.abs(mx.sum(losses, axis=1))
        profit_factor = mx.where(gross_loss > 0, gross_profit / gross_loss, 100.0)

        # Sharp Ratio (simplified)
        mean_ret = mx.mean(strat_returns, axis=1)
        std_ret = mx.std(strat_returns, axis=1)
        sharpe = mx.where(
            std_ret > 0, mean_ret / std_ret * mx.sqrt(float(252)), 0.0
        )  # Assume daily for annualization

        # 5. Bring back to CPU
        results = []
        final_rets_np = np.array(final_returns)
        max_dds_np = np.array(max_drawdowns)
        sharpe_np = np.array(sharpe)
        pf_np = np.array(profit_factor)

        for i in range(len(indicators)):
            results.append(
                {
                    "total_return": float(final_rets_np[i]) - 1.0,
                    "max_drawdown": float(max_dds_np[i]),
                    "sharpe_ratio": float(sharpe_np[i]),
                    "profit_factor": float(pf_np[i]),
                    "success": bool(final_rets_np[i] > 1.0 and max_dds_np[i] < 0.2),
                    "metrics": {
                        "total_return": float(final_rets_np[i]) - 1.0,
                        "max_drawdown": float(max_dds_np[i]),
                        "sharpe_ratio": float(sharpe_np[i]),
                        "profit_factor": float(pf_np[i]),
                    },
                }
            )

        return results

    def backtest_scenarios(
        self,
        indicator: BaseIndicator,
        scenarios: list[pd.DataFrame],
        executor: ParallelExecutor | None = None,
    ) -> list[dict[str, Any]]:
        """Run one indicator across many data scenarios on GPU."""
        return run_scenarios_backtest(indicator, scenarios, executor)

    def backtest_lazy_scenarios(
        self,
        indicator: BaseIndicator,
        n_scenarios: int,
        executor: ParallelExecutor,
        block_size: int | None = None,
        base_seed: int = 42
    ) -> list[dict[str, Any]]:
        """Run backtest with lazy scenario generation (Block Bootstrap)."""
        return run_lazy_backtest(
            indicator=indicator,
            n_scenarios=n_scenarios,
            executor=executor,
            block_size=block_size,
            base_seed=base_seed,
        )
