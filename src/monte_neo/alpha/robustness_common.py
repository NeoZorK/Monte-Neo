"""Shared helpers for the robustness checks (family E): one comparable net long-short return series."""

from __future__ import annotations

import numpy as np

from monte_neo.alpha._core import leg_weights, quantile_index
from monte_neo.alpha.implementability_common import (
    ann_return,
    ann_sharpe,
    gross_series,
    simple_returns,
    weight_changes,
)
from monte_neo.alpha.panel import Panel

DEFAULT_COST_BPS = 10.0
MIN_BARS = 30

__all__ = ["DEFAULT_COST_BPS", "MIN_BARS", "ann_return", "ann_sharpe", "periods_per_year", "rnd", "spread", "spread_parts", "step_seconds"]


def spread_parts(
    close: np.ndarray, scores: np.ndarray, quantiles: int, cost_bps: float = DEFAULT_COST_BPS
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Net returns of the top-minus-bottom quantile portfolio and the pieces they are built from.

    Weights decided at ``t - 1`` earn bar ``t``; each unit of weight change costs ``cost_bps``.

    Args:
        close: Prices, shape (T, N).
        scores: Scores, shape (T, N).
        quantiles: Number of quantile buckets.
        cost_bps: One-way cost in basis points per unit of weight traded.

    Returns:
        ``(net, weights, returns, cost)``: net per-bar returns (T,), weights (T, N), simple
        returns (T, N) and the per-bar cost (T,).
    """
    valid = np.isfinite(scores) & np.isfinite(close)
    w = leg_weights(quantile_index(scores, valid, quantiles), quantiles)
    ret = simple_returns(close)
    cost = np.abs(weight_changes(w)).sum(axis=1) * cost_bps / 1e4
    return gross_series(w, ret) - cost, w, ret, cost


def spread(close: np.ndarray, scores: np.ndarray, quantiles: int, cost_bps: float = DEFAULT_COST_BPS) -> np.ndarray:
    """Per-bar net returns of the score's long-short portfolio (gross minus turnover cost)."""
    return spread_parts(close, scores, quantiles, cost_bps)[0]


def step_seconds(panel: Panel) -> float:
    """Median spacing of the panel dates in seconds, whatever the datetime unit (ns, us, s)."""
    if len(panel.dates) < 2:
        return 86400.0
    secs = panel.dates.values.astype("datetime64[s]").astype(np.int64)
    return float(np.median(np.diff(secs)))


def periods_per_year(panel: Panel) -> float:
    """Bars per year from the date spacing (daily or slower-than-1.5-day bars: 252 for daily)."""
    step = step_seconds(panel)
    if step <= 0:
        return 252.0
    return 252.0 if step <= 1.5 * 86400 and step >= 0.9 * 86400 else 365.25 * 86400 / step


def rnd(x: float, digits: int = 4) -> float | None:
    """Round a float for a details dict; non-finite becomes ``None``."""
    return round(float(x), digits) if np.isfinite(x) else None
