"""Lazy GPU backtesting helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import mlx.core as mx
import numpy as np

from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.workers import _generate_lazy_scenario_wrapper
from monte_neo.utils.parallel import ParallelExecutor

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator


def backtest_lazy_scenarios(
    indicator: BaseIndicator,
    n_scenarios: int,
    executor: ParallelExecutor,
    block_size: int | None = None,
    base_seed: int = 42,
    use_sl_tp: bool = False,
    sl_pct: float = 0.0,
    tp_pct: float = 0.0,
) -> list[dict[str, Any]]:
    """Run backtest with lazy scenario generation (Block Bootstrap).

    Args:
        indicator: Indicator to test.
        n_scenarios: Number of scenarios.
        executor: Shared parallel executor.
        block_size: Optional block size for bootstrap.
        base_seed: Base seed for reproducible scenarios.
        use_sl_tp: Whether to apply Stop Loss and Take Profit.
        sl_pct: Stop Loss percentage.
        tp_pct: Take Profit percentage.

    Returns:
        List of result dictionaries.
    """
    seeds = [base_seed + i for i in range(n_scenarios)]
    tasks = [(indicator, seed, block_size) for seed in seeds]

    raw_results = executor.map(_generate_lazy_scenario_wrapper, tasks)

    if use_sl_tp:
        # SL/TP requires path-dependent calculation (CPU)
        calc = MetricsCalculator()
        results = []
        for res in raw_results:
            if res is None:
                results.append({
                    "total_return": -1.0, "max_drawdown": 1.0, "profit_factor": 0.0,
                    "passed": False, "metrics": {}
                })
                continue
            
            sigs, df = res # In lazy wrapper, it returns (signals, df)
            
            # Ensure sigs is converted to DataFrame if needed
            if not isinstance(sigs, pd.DataFrame):
                sigs_df = pd.DataFrame({"signal": sigs}, index=df.index)
            else:
                sigs_df = sigs

            metrics = calc.calculate_all(
                df, sigs_df, use_sl_tp=use_sl_tp, sl_pct=sl_pct, tp_pct=tp_pct
            )
            results.append({
                "total_return": metrics.get("total_return", -1.0),
                "max_drawdown": metrics.get("max_drawdown", 1.0),
                "profit_factor": metrics.get("profit_factor", 0.0),
                "passed": bool(metrics.get("total_return", -1.0) > 0.0 and metrics.get("max_drawdown", 1.0) < 0.2),
                "metrics": metrics
            })
        return results

    signal_list = []
    returns_list = []

    for res in raw_results:
        if res is None:
            continue
        sigs, rets = res
        sig_vals = sigs.reshape(-1).astype(np.float32)
        sig_vals = sig_vals[:-1]
        signal_list.append(sig_vals)
        returns_list.append(rets.astype(np.float32))

    if not signal_list:
        return []

    max_len = max(len(s) for s in signal_list)
    padded_signals = []
    padded_returns = []

    for s, r in zip(signal_list, returns_list):
        pad_width = max_len - len(s)
        if pad_width > 0:
            padded_signals.append(np.pad(s, (0, pad_width), "constant", constant_values=0))
            padded_returns.append(np.pad(r, (0, pad_width), "constant", constant_values=0))
        else:
            padded_signals.append(s)
            padded_returns.append(r)

    signal_matrix = mx.array(np.stack(padded_signals))
    returns_matrix = mx.array(np.stack(padded_returns))

    strat_returns = signal_matrix * returns_matrix

    equity_curves = mx.exp(
        mx.cumsum(mx.log1p(mx.clip(strat_returns, -0.9, 10.0)), axis=1)
    )

    final_rets = np.array(equity_curves[:, -1])

    running_max = mx.cummax(equity_curves, axis=1)
    max_dds = np.array(mx.max((running_max - equity_curves) / running_max, axis=1))

    wins = mx.where(strat_returns > 0, strat_returns, 0)
    losses = mx.where(strat_returns < 0, strat_returns, 0)
    gross_profit = mx.sum(wins, axis=1)
    gross_loss = mx.abs(mx.sum(losses, axis=1))
    profit_factor = np.array(mx.where(gross_loss > 0, gross_profit / gross_loss, 100.0))

    results = []
    for i in range(len(signal_list)):
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
