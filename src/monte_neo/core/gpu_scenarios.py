"""GPU scenario backtesting helper."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import mlx.core as mx
import numpy as np
import pandas as pd

from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.workers import _generate_signals_wrapper
from monte_neo.utils.parallel import ParallelExecutor

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator


def normalize_signal_array(
    signals: Any,
    target_len: int,
) -> np.ndarray:
    """Normalize signals to numpy array of target length."""
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


def run_scenarios_backtest(
    indicator: BaseIndicator,
    scenarios: list[pd.DataFrame],
    executor: ParallelExecutor | None = None,
    use_sl_tp: bool = False,
    sl_pct: float = 0.0,
    tp_pct: float = 0.0,
) -> list[dict[str, Any]]:
    """Run one indicator across many data scenarios on GPU."""
    if use_sl_tp:
        # Optimization: Use parallelized batch Numba for SL/TP on multiple scenarios
        # This is much faster than the previous Python loop

        # 1. Get Signals (CPU parallelized)
        tasks = [(indicator, df) for df in scenarios]
        if executor is None:
            local_executor = ParallelExecutor()
            raw_signals = local_executor.map(_generate_signals_wrapper, tasks)
        else:
            raw_signals = executor.map(_generate_signals_wrapper, tasks)

        # 2. Prepare Data and Signal Matrix
        max_len = max(len(df) for df in scenarios)

        # We need a unified price matrix for Numba batch
        # Since scenarios can have different prices, we pad them
        close_matrix = np.zeros((len(scenarios), max_len), dtype=np.float64)
        high_matrix = np.zeros((len(scenarios), max_len), dtype=np.float64)
        low_matrix = np.zeros((len(scenarios), max_len), dtype=np.float64)
        signal_matrix = np.zeros((len(scenarios), max_len), dtype=np.int32)

        for i, df in enumerate(scenarios):
            l = len(df)
            close_matrix[i, :l] = df["close"].values
            high_matrix[i, :l] = df["high"].values
            low_matrix[i, :l] = df["low"].values
            signal_matrix[i, :l] = normalize_signal_array(raw_signals[i], l).astype(np.int32)

        # 3. Run Batch Calculation (Multi-scenario version)
        # We use calculate_batch_multi_price_fast because each scenario has its own prices
        batch_metrics = MetricsCalculator.calculate_batch_multi_price_fast(
            close_matrix,
            high_matrix,
            low_matrix,
            signal_matrix,
            use_sl_tp,
            sl_pct,
            tp_pct
        )

        results = []
        for i in range(len(scenarios)):
            total_return = float(batch_metrics[i, 0])
            max_dd = float(batch_metrics[i, 1])
            pf = float(batch_metrics[i, 2])
            trade_count = int(batch_metrics[i, 3])

            results.append({
                "total_return": total_return,
                "max_drawdown": max_dd,
                "profit_factor": pf,
                "passed": bool(total_return > 0.0 and max_dd < 0.2),
                "metrics": {
                    "total_return": total_return,
                    "max_drawdown": max_dd,
                    "profit_factor": pf,
                    "trade_count": trade_count,
                }
            })
        return results

    # 1. Prepare Returns Matrix (S_scenarios x T_bars)
    # Assuming OHLCV format, we pre-calculate returns for all scenarios
    returns_list = []
    for df in scenarios:
        rets = (df["close"].values[1:] / df["close"].values[:-1]) - 1
        returns_list.append(rets.astype(np.float32))

    # Handle variable lengths by padding with 0
    if not returns_list:
        return []

    max_len = max(len(r) for r in returns_list)
    padded_returns = []

    for r in returns_list:
        pad_width = max_len - len(r)
        if pad_width > 0:
            padded_returns.append(np.pad(r, (0, pad_width), "constant", constant_values=0))
        else:
            padded_returns.append(r)

    # Matrix: (S, T-1)
    returns_matrix = mx.array(np.stack(padded_returns))

    # 2. Get Signals (CPU parallelized)
    # We use ParallelExecutor to speed up signal generation for many scenarios
    signal_list = []

    # Prepare args for parallel execution
    # (indicator is pickleable usually)
    tasks = [(indicator, df) for df in scenarios]

    # Use ProcessPoolExecutor for CPU-bound signal generation
    # Adjust n_workers as needed, default is usually fine
    # NOTE: Parallelizing might have overhead for small DataFrames.
    # But for 1000 scenarios, it should help.

    # If scenarios are few, do serial
    if len(scenarios) < 50:
        raw_signals = []
        for df in scenarios:
            try:
                raw_signals.append(indicator.generate_signals(df))
            except Exception:
                raw_signals.append(None)
    else:
        # Parallel execution
        if executor is None:
            local_executor = ParallelExecutor()
            # Map returns results in order
            raw_signals = local_executor.map(_generate_signals_wrapper, tasks)
        else:
            # Use shared executor
            raw_signals = executor.map(_generate_signals_wrapper, tasks)

    for sigs in raw_signals:
        signal_list.append(normalize_signal_array(sigs, max_len))

    # Matrix: (S, T-1)
    signal_matrix = mx.array(np.stack(signal_list))

    # 3. Massive GPU calc
    strat_returns = signal_matrix * returns_matrix

    # Vectorized metrics
    equity_curves = mx.exp(
        mx.cumsum(mx.log1p(mx.clip(strat_returns, -0.9, 10.0)), axis=1)
    )

    final_rets = np.array(equity_curves[:, -1])

    # Max DD
    # running_max = mx.maximum.accumulate(equity_curves, axis=1) # type: ignore
    running_max = mx.cummax(equity_curves, axis=1)
    max_dds = np.array(mx.max((running_max - equity_curves) / running_max, axis=1))

    # Profit Factor
    wins = mx.where(strat_returns > 0, strat_returns, 0)
    losses = mx.where(strat_returns < 0, strat_returns, 0)
    gross_profit = mx.sum(wins, axis=1)
    gross_loss = mx.abs(mx.sum(losses, axis=1))
    profit_factor = np.array(mx.where(gross_loss > 0, gross_profit / gross_loss, 100.0))

    results = []
    for i in range(len(scenarios)):
        results.append(
            {
                "total_return": float(final_rets[i]) - 1.0,
                "max_drawdown": float(max_dds[i]),
                "profit_factor": float(profit_factor[i]),
                "passed": bool(final_rets[i] > 1.0 and max_dds[i] < 0.2),
                "metrics": {
                    "total_return": float(final_rets[i]) - 1.0,
                    "max_drawdown": float(max_dds[i]),
                    "profit_factor": float(profit_factor[i]),
                },
            }
        )
    return results
