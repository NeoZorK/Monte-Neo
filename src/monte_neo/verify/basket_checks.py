"""Baskets: is the profit stock selection, or market timing and market beta?

* **Selection vs timing.** With weights ``w_i`` held over a bar and returns ``r_i``, the bar's P&L splits exactly into
  ``sum(w) * mean(r)`` (net exposure times the equal-weight market return: *timing*) and
  ``sum((w_i - mean(w)) * (r_i - mean(r)))`` (cross-sectional covariance of weights and returns: *selection*), the
  identity behind Grinold and Kahn's decomposition of active return. A basket whose mean P&L is almost all timing, with
  a selection term not distinguishable from zero, is a market-timing strategy, not a stock-picking one.
* **Alpha after two betas.** Regress the strategy on the equal-weight basket and on a reference asset (for example BTC)
  with Newey-West errors (see :mod:`monte_neo.verify.alpha_beta`); alpha must stay significantly positive.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from monte_neo.verify.alpha_beta import MIN_OBS, T_MIN, Z95
from monte_neo.verify.checks import check

TIMING_SHARE = 0.8


def nw_multi(y: np.ndarray, x: np.ndarray) -> dict[str, np.ndarray]:
    """OLS of ``y`` on a constant and the columns of ``x`` with Newey-West errors: coefficients and standard errors."""
    n = y.size
    xm = np.column_stack([np.ones(n), x])
    coef = np.linalg.lstsq(xm, y, rcond=None)[0]
    e = y - xm @ coef
    lags = int(math.floor(4 * (n / 100.0) ** (2 / 9)))
    u = xm * e[:, None]
    s = u.T @ u
    for k in range(1, lags + 1):
        g = u[k:].T @ u[:-k]
        s += (1 - k / (lags + 1)) * (g + g.T)
    bread = np.linalg.inv(xm.T @ xm)
    cov = bread @ s @ bread
    return {"coef": coef, "se": np.sqrt(np.maximum(np.diag(cov), 1e-30))}


def selection_timing(weights: np.ndarray, returns: np.ndarray) -> dict[str, np.ndarray]:
    """Per-bar timing and selection terms; ``weights`` and ``returns`` are (bars, symbols), NaN return = not tradable."""
    w, r = np.asarray(weights, dtype=np.float64), np.asarray(returns, dtype=np.float64)
    valid = np.isfinite(r)
    n = np.maximum(valid.sum(axis=1), 1)
    r0, w0 = np.where(valid, r, 0.0), np.where(valid, w, 0.0)
    rbar, wbar = r0.sum(axis=1) / n, w0.sum(axis=1) / n
    timing = w0.sum(axis=1) * rbar
    total = (w0 * r0).sum(axis=1)
    return {"timing": timing, "selection": total - timing, "total": total}


def selection_timing_row(weights: np.ndarray, returns: np.ndarray, periods_per_year: float) -> dict[str, Any]:
    """Row ``selection_vs_timing_basket``: ``warn`` when the mean P&L is over 80 % timing and selection is not significant."""
    if np.asarray(weights).ndim != 2 or np.asarray(weights).shape[1] < 2:
        return check("selection_vs_timing_basket", "statistics", "skip", "one instrument: no cross-section to select from")
    d = selection_timing(weights, returns)
    n = d["total"].size
    if n < MIN_OBS:
        return check("selection_vs_timing_basket", "statistics", "skip", f"only {n} bars")
    mt, ms = float(d["timing"].mean()), float(d["selection"].mean())
    sd = float(d["selection"].std(ddof=1))
    t_sel = ms / (sd / math.sqrt(n)) if sd > 1e-12 else 0.0
    total = mt + ms
    det = {"timing_annual": mt * periods_per_year, "selection_annual": ms * periods_per_year,
           "selection_t": t_sel, "timing_share": mt / total if total > 0 else None, "bars": n}
    if total <= 0.0:
        return check("selection_vs_timing_basket", "statistics", "skip", "the basket does not earn on average", det)
    text = (f"annual P&L: market timing {mt * periods_per_year:+.1%}, selection {ms * periods_per_year:+.1%} "
            f"(selection t={t_sel:.1f}); {mt / total:.0%} of the mean P&L is timing")
    if mt / total > TIMING_SHARE and t_sel < T_MIN:
        return check("selection_vs_timing_basket", "statistics", "warn", "market timing, not selection: " + text, det)
    if t_sel >= T_MIN:
        return check("selection_vs_timing_basket", "statistics", "pass", text, det)
    return check("selection_vs_timing_basket", "statistics", "info", "selection is not significant: " + text, det)


def alpha_two_betas_row(r: np.ndarray, basket: np.ndarray, reference: np.ndarray, periods_per_year: float, ref_name: str) -> dict[str, Any]:
    """Row ``alpha_after_reference``: alpha after beta to the equal-weight basket and to ``reference`` jointly."""
    n = min(r.size, basket.size, reference.size)
    y, x = np.asarray(r[-n:], dtype=np.float64), np.column_stack([basket[-n:], reference[-n:]])
    if n < MIN_OBS:
        return check("alpha_after_reference", "statistics", "skip", f"only {n} bars")
    if np.std(y) <= 0 or np.any(np.std(x, axis=0) <= 0) or abs(np.corrcoef(x.T)[0, 1]) > 0.999:
        return check("alpha_after_reference", "statistics", "skip", "a series is constant or the two benchmarks are identical")
    fit = nw_multi(y, x)
    a, se = float(fit["coef"][0]), float(fit["se"][0])
    ppy = float(periods_per_year)
    det = {"n": n, "beta_basket": float(fit["coef"][1]), "beta_reference": float(fit["coef"][2]), "reference": ref_name,
           "alpha_annual": a * ppy, "alpha_ci95_annual": [(a - Z95 * se) * ppy, (a + Z95 * se) * ppy], "alpha_t": a / se}
    text = (f"beta {det['beta_basket']:.2f} to the basket and {det['beta_reference']:.2f} to {ref_name}, annual alpha "
            f"{a * ppy:+.1%} (95% interval {det['alpha_ci95_annual'][0]:+.1%} to {det['alpha_ci95_annual'][1]:+.1%}, t={a / se:.1f})")
    if a / se >= T_MIN and det["alpha_ci95_annual"][0] > 0:
        return check("alpha_after_reference", "statistics", "pass", text, det)
    return check("alpha_after_reference", "statistics", "warn", f"alpha is not significant after both betas: {text}", det)


__all__ = ["TIMING_SHARE", "alpha_two_betas_row", "nw_multi", "selection_timing", "selection_timing_row"]
