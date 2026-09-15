"""Summary metrics helpers for bar backtest results."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.backtest.trades import trade_stats


def summarize_equity(equity: np.ndarray, *, initial_cash: float) -> dict[str, float]:
    """Compute total return and max drawdown from an equity curve."""
    eq = np.asarray(equity, dtype=np.float64)
    if eq.size == 0:
        raise ValueError("empty equity")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    if initial_cash <= 0.0:
        raise ValueError("initial_cash must be positive")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / np.maximum(peak, 1e-12)
    return {
        "total_return": float(eq[-1] / initial_cash - 1.0),
        "max_drawdown": float(np.max(dd)),
        "final_equity": float(eq[-1]),
    }


def sharpe_from_equity(
    equity: np.ndarray, *, periods_per_year: float = 365.0 * 24.0 * 60.0
) -> float:
    """Annualized Sharpe from bar equity returns (risk-free = 0)."""
    eq = np.asarray(equity, dtype=np.float64)
    if eq.size < 2:
        return 0.0  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    rets = np.diff(eq) / np.maximum(eq[:-1], 1e-12)
    std = float(np.std(rets))
    if std <= 0.0:
        return 0.0
    return float(np.mean(rets) / std * np.sqrt(periods_per_year))


def summarize_backtest(
    equity: np.ndarray,
    trades: list[dict[str, Any]],
    *,
    initial_cash: float,
    max_drawdown: float | None = None,
) -> dict[str, float]:
    """Unified summary: equity path + trade stats (bps costs stay on engine)."""
    base = summarize_equity(equity, initial_cash=initial_cash)
    if max_drawdown is not None:
        base["max_drawdown"] = float(max_drawdown)
    base["sharpe"] = sharpe_from_equity(equity)
    base.update(trade_stats(trades))
    return base


def assert_fee_hurts_return(zero_fee: dict[str, Any], with_fee: dict[str, Any]) -> None:
    """Invariant: positive fees must not improve total_return vs zero-fee path."""
    if float(with_fee["total_return"]) > float(zero_fee["total_return"]) + 1e-12:
        raise AssertionError("fees improved return — execution model bug")
