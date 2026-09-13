"""Summary metrics helpers for bar backtest results."""

from __future__ import annotations

from typing import Any

import numpy as np


def summarize_equity(equity: np.ndarray, *, initial_cash: float) -> dict[str, float]:
    """Compute total return and max drawdown from an equity curve."""
    eq = np.asarray(equity, dtype=np.float64)
    if eq.size == 0:
        raise ValueError("empty equity")
    if initial_cash <= 0.0:
        raise ValueError("initial_cash must be positive")
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / np.maximum(peak, 1e-12)
    return {
        "total_return": float(eq[-1] / initial_cash - 1.0),
        "max_drawdown": float(np.max(dd)),
        "final_equity": float(eq[-1]),
    }


def assert_fee_hurts_return(zero_fee: dict[str, Any], with_fee: dict[str, Any]) -> None:
    """Invariant: positive fees must not improve total_return vs zero-fee path."""
    if float(with_fee["total_return"]) > float(zero_fee["total_return"]) + 1e-12:
        raise AssertionError("fees improved return — execution model bug")
