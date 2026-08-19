"""Utility functions for metrics calculation."""

from __future__ import annotations

import numpy as np


def max_consecutive(pnls: list[float] | np.ndarray, wins: bool) -> int:
    """Calculate max consecutive wins or losses.

    Args:
        pnls: List of P&L values.
        wins: If True, count wins; else count losses.

    Returns:
        Maximum consecutive count.
    """
    max_count = 0
    current = 0

    for pnl in pnls:
        is_win = pnl > 0
        if is_win == wins:
            current += 1
            max_count = max(max_count, current)
        else:
            current = 0

    return max_count


def calculate_recovery_factor(total_return: float, max_dd: float) -> float:
    """Calculate recovery factor.

    Args:
        total_return: Total return percentage.
        max_dd: Maximum drawdown (0.0 to 1.0).

    Returns:
        Recovery factor (total_return / max_dd).
    """
    if max_dd == 0:
        return 0.0
    return float(total_return / max_dd)


def calculate_calmar_ratio(
    avg_return: float, max_dd: float, periods_per_year: int = 252
) -> float:
    """Calculate Calmar ratio.

    Args:
        avg_return: Average return per period.
        max_dd: Maximum drawdown.
        periods_per_year: Trading periods per year.

    Returns:
        Calmar ratio (annual_return / max_drawdown).
    """
    if max_dd == 0:
        return 0.0

    annual_return = avg_return * periods_per_year
    return float(annual_return / max_dd)


def get_empty_metrics() -> dict[str, float]:
    """Return empty metrics when no trades."""
    return {
        "profit_factor": 0.0,
        "total_return": 0.0,
        "avg_return": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "max_drawdown": 0.0,
        "avg_drawdown": 0.0,
        "recovery_factor": 0.0,
        "calmar_ratio": 0.0,
        "winrate": 0.0,
        "expectancy": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "win_loss_ratio": 0.0,
        "trade_count": 0.0,
        "consecutive_wins": 0.0,
        "consecutive_losses": 0.0,
    }
