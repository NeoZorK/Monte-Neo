"""Funding and borrow as rate series (perpetual futures funding, stock-borrow fees), applied to a held position.

The engine's ``funding_bps_per_bar`` is one constant. Real funding changes with the market and flips sign; borrow fees
for hard-to-borrow names spike. This module applies a *per-bar series* (or a constant) to the weight held over each bar:

* funding: a long pays ``rate`` when it is positive and receives it when negative; a short is the mirror image;
* borrow: only a short position pays ``borrow`` (per bar, always >= 0).

Sign convention follows the perpetual-swap funding mechanism (the long pays the short when the funding rate is positive).
The row ``funding_borrow_stress`` reports the return before and after, and warns when funding/borrow turns a profit into
a loss. It does not model liquidations or margin calls.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.verify.checks import check


def _per_bar(rate: float | np.ndarray, n: int, name: str) -> np.ndarray:
    arr = np.full(n, float(rate)) if np.ndim(rate) == 0 else np.asarray(rate, dtype=np.float64)
    if arr.shape != (n,):
        raise ValueError(f"{name} must be a number or one value per bar ({n}), got shape {arr.shape}")
    if not np.isfinite(arr).all():
        raise ValueError(f"{name} contains non-finite values")
    return arr


def funding_borrow_drag(weights: np.ndarray, funding_bps: float | np.ndarray = 0.0, borrow_bps: float | np.ndarray = 0.0) -> np.ndarray:
    """Per-bar return cost (a positive number is a cost) of holding ``weights`` (weight held over each bar).

    Raises:
        ValueError: A rate array of the wrong length, non-finite rates, or a negative borrow fee.
    """
    w = np.asarray(weights, dtype=np.float64)
    f, b = _per_bar(funding_bps, w.size, "funding_bps"), _per_bar(borrow_bps, w.size, "borrow_bps")
    if (b < 0).any():
        raise ValueError("borrow_bps must be >= 0")
    return (w * f + np.maximum(-w, 0.0) * b) / 1e4


def funding_stress_row(returns: np.ndarray, weights: np.ndarray, funding_bps: float | np.ndarray = 0.0,
                       borrow_bps: float | np.ndarray = 0.0) -> dict[str, Any]:
    """Check row ``funding_borrow_stress``: return before and after the funding/borrow drag.

    ``returns[t]`` is the strategy return over bar ``t`` and ``weights[t]`` the weight held over that bar. ``warn`` when a
    profit becomes a loss; ``skip`` when it was not profitable to begin with.
    """
    r = np.asarray(returns, dtype=np.float64)
    drag = funding_borrow_drag(weights, funding_bps, borrow_bps)
    if drag.size != r.size:
        raise ValueError("returns and weights must have the same length")
    before, after = float(np.prod(1.0 + r) - 1.0), float(np.prod(1.0 + r - drag) - 1.0)
    det = {"return_before": before, "return_after": after, "total_drag": float(drag.sum()),
           "mean_funding_bps": float(np.mean(_per_bar(funding_bps, r.size, "funding_bps"))),
           "mean_borrow_bps": float(np.mean(_per_bar(borrow_bps, r.size, "borrow_bps")))}
    if before <= 0.0:
        return check("funding_borrow_stress", "economics", "skip", "not profitable before funding and borrow", det)
    text = f"total return {before:+.1%} before funding and borrow, {after:+.1%} after (drag {drag.sum():+.2%})"
    if after <= 0.0:
        return check("funding_borrow_stress", "economics", "warn", "funding and borrow cost the whole profit: " + text, det)
    return check("funding_borrow_stress", "economics", "pass", text, det)


__all__ = ["funding_borrow_drag", "funding_stress_row"]
