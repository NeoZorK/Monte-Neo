"""Tail dependence and correlation breakdown of a set of strategy return series.

* :func:`tail_dependence` is the empirical lower- and upper-tail dependence coefficient at quantile ``q``,
  ``lambda(q) = P(U_j <= q | U_i <= q)`` on the rank-transformed (pseudo-observation) series, averaged over pairs
  (Joe 1997, "Multivariate models and dependence concepts"; Schmidt and Stadtmuller 2006, "Non-parametric estimation of
  tail dependence", Scandinavian J. Statistics 33). Two independent series give ``q``; two clones give 1. The estimate
  is at a finite ``q`` (the limit ``q -> 0`` is not estimable from a short history); the row reports how far it sits
  above ``q``.
* :func:`stressed_cvar` is the Gaussian expected shortfall of the equal-weight (or given-weight) ensemble when every
  pairwise correlation is raised to a stress level (default: the larger of the observed tail correlation and 0.8
  times the strongest pairwise correlation). Correlations rise in sell-offs (Longin and Solnik 2001, "Extreme
  correlation of international equity markets", Journal of Finance 56(2)); the diversification of a calm sample is
  not the diversification of a crash.

``warn`` only; a history with fewer than 5 tail bars per series is "not assessed".
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any

import numpy as np

from monte_neo.verify.checks import check

TAIL_Q = 0.05
MIN_TAIL_BARS = 5
EXCESS_WARN = 0.25  # lambda(q) this far above q (independence) warns
STRESS_RATIO_WARN = 1.5  # stressed ES over normal ES


def _ranks(m: np.ndarray) -> np.ndarray:
    order = np.argsort(np.argsort(m, axis=1), axis=1)
    return (order + 1.0) / (m.shape[1] + 1.0)


def tail_dependence(mat: np.ndarray, q: float = TAIL_Q) -> dict[str, Any]:
    """Mean pairwise lower and upper tail dependence at quantile ``q``.

    Raises:
        ValueError: Fewer than 2 series, fewer than 20 bars, or ``q`` outside (0, 0.5).
    """
    m = np.asarray(mat, dtype=np.float64)
    if m.ndim != 2 or m.shape[0] < 2 or m.shape[1] < 20:
        raise ValueError("need at least 2 series and 20 bars")
    if not 0.0 < q < 0.5:
        raise ValueError("q must be in (0, 0.5)")
    u = _ranks(m)
    k = m.shape[0]
    lower, upper, pairs = [], [], 0
    for i in range(k):
        lo_i, up_i = u[i] <= q, u[i] >= 1.0 - q
        if lo_i.sum() < MIN_TAIL_BARS:
            return {"status": "skip", "reason": f"fewer than {MIN_TAIL_BARS} tail bars at q={q}", "q": q}
        for j in range(i + 1, k):
            lower.append(float(np.mean(u[j][lo_i] <= q)))
            upper.append(float(np.mean(u[j][up_i] >= 1.0 - q)))
            pairs += 1
    return {"status": "ok", "q": float(q), "lower": float(np.mean(lower)), "upper": float(np.mean(upper)),
            "lower_max": float(np.max(lower)), "independence": float(q), "pairs": pairs, "tail_bars": int(math.floor(q * m.shape[1]))}


def stressed_cvar(mat: np.ndarray, weights: np.ndarray | None = None, alpha: float = 0.05, stress_corr: float | None = None) -> dict[str, Any]:
    """Gaussian ES of the ensemble with the correlations raised to ``stress_corr`` (never lowered)."""
    m = np.asarray(mat, dtype=np.float64)
    k = m.shape[0]
    w = np.full(k, 1.0 / k) if weights is None else np.asarray(weights, dtype=np.float64) / np.sum(weights)
    sd = m.std(axis=1, ddof=1)
    corr = np.nan_to_num(np.corrcoef(m), nan=0.0)
    off = corr[~np.eye(k, dtype=bool)]
    ens = w @ m
    tail = ens <= np.quantile(ens, 0.10)
    tail_corr = float(np.nan_to_num(np.corrcoef(m[:, tail]), nan=0.0)[~np.eye(k, dtype=bool)].mean()) if tail.sum() >= 3 else float(off.mean())
    level = float(stress_corr) if stress_corr is not None else max(tail_corr, 0.8 * float(off.max()))
    stressed = np.maximum(corr, level)
    np.fill_diagonal(stressed, 1.0)

    def es(c: np.ndarray) -> float:
        sigma = math.sqrt(max(float((w * sd) @ c @ (w * sd)), 0.0))
        z = NormalDist().inv_cdf(alpha)
        return float(-(w @ m.mean(axis=1)) + sigma * math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi) / alpha)  # loss as a positive number

    base, hard = es(corr), es(stressed)
    return {"stress_correlation": level, "normal_es": base, "stressed_es": hard, "ratio": hard / base if base > 0 else None}


def tail_dependence_row(td: dict[str, Any]) -> dict[str, Any]:
    """``tail_dependence``: warn when the strategies fall together far more often than independence would give."""
    if td.get("status") != "ok":
        return check("tail_dependence", "risk", "skip", "not assessed: " + td.get("reason", "too little history"), td)
    excess = td["lower"] - td["independence"]
    text = (f"lower-tail dependence {td['lower']:.2f} at q={td['q']:.0%} (independent series: {td['independence']:.2f}), "
            f"upper {td['upper']:.2f}, strongest pair {td['lower_max']:.2f}")
    if excess > EXCESS_WARN:
        return check("tail_dependence", "risk", "warn", "the strategies fall together: " + text, td)
    return check("tail_dependence", "risk", "pass", text, td)


def correlation_stress_row(res: dict[str, Any]) -> dict[str, Any]:
    """``correlation_breakdown_stress``: warn when stressed correlations raise the ensemble's tail loss by half or more."""
    if res.get("ratio") is None:
        return check("correlation_breakdown_stress", "risk", "skip", "not assessed: the ensemble has no tail loss to scale", res)
    text = (f"ensemble expected shortfall {res['normal_es']:.2%} per bar normally, {res['stressed_es']:.2%} when pairwise "
            f"correlations rise to {res['stress_correlation']:.2f} ({res['ratio']:.2f}x)")
    if res["ratio"] >= STRESS_RATIO_WARN:
        return check("correlation_breakdown_stress", "risk", "warn", "diversification fails in a sell-off: " + text, res)
    return check("correlation_breakdown_stress", "risk", "pass", text, res)


__all__ = ["EXCESS_WARN", "STRESS_RATIO_WARN", "TAIL_Q", "correlation_stress_row", "stressed_cvar", "tail_dependence", "tail_dependence_row"]
