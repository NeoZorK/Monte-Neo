"""Structural-break tests for a spread: CUSUM, Chow / sup-Wald and a simplified Bai-Perron search.

All three work on a *stationary* series (a spread, or a spread with a frozen hedge ratio) and ask whether its mean moved.
Spreads are strongly autocorrelated, so every statistic is scaled by a long-run variance estimated after AR(1)
pre-whitening (Andrews & Monahan 1992); scaling by the plain variance would flag a break in almost every honest pair.

Sources and critical values:

* **OLS-CUSUM** (Ploberger & Kramer 1992): ``max |S_t| / (omega sqrt(n))`` where ``S_t`` is the partial sum of the
  demeaned series. The null limit is the supremum of a Brownian bridge: 10 / 5 / 1 % = 1.2238 / 1.3581 / 1.6276
  (Kolmogorov distribution).
* **Chow** (1960) with a known date, as a Wald statistic: asymptotically chi-square with one degree of freedom for a
  mean shift (3.841 at 5 %, 6.635 at 1 %).
* **Sup-Wald** over unknown dates with 15 % trimming (Quandt 1960; Andrews 1993; Bai & Perron 2003, Table 1, 1|0, one
  parameter): 10 / 5 / 2.5 / 1 % = 7.04 / 8.58 / 10.18 / 12.29.
* **Bai-Perron, simplified**: sequential tests of one more break against the previous number (Bai & Perron 1998, 2003;
  sup-F(l+1|l) 5 % = 8.58, 10.13, 11.14, 11.83 and 1 % = 12.29, 13.89, 14.80, 15.28 for l = 0..3). Breaks are found
  by sequential splitting, not by the dynamic-programming global optimum, and the sequential critical values are
  approximate.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

TRIM = 0.15
CUSUM_CRITICAL = {0.10: 1.2238, 0.05: 1.3581, 0.01: 1.6276}
SUPW_CRITICAL = {0.10: 7.04, 0.05: 8.58, 0.01: 12.29}
SEQ_CRITICAL = {0.05: (8.58, 10.13, 11.14, 11.83), 0.01: (12.29, 13.89, 14.80, 15.28)}
CHOW_CRITICAL = {0.05: 3.841, 0.01: 6.635}
MIN_POINTS = 60
PHI_CAP = 0.97


def prewhitened_lrv(x: np.ndarray) -> float:
    """Long-run variance of a series that is already centred, from an AR(1) fit (``sigma_e^2 / (1 - phi)^2``)."""
    e = np.asarray(x, dtype=np.float64)
    denom = float(e[:-1] @ e[:-1])
    phi = float(np.clip(float(e[1:] @ e[:-1]) / denom if denom > 0 else 0.0, -PHI_CAP, PHI_CAP))
    innov = e[1:] - phi * e[:-1]
    return float(max(innov @ innov / max(innov.size, 1), 1e-300) / (1.0 - phi) ** 2)


def cusum_test(series: np.ndarray) -> dict[str, Any]:
    """OLS-CUSUM test of a stable mean.

    Returns:
        ``stat``, ``index`` (the bar after which the partial sum peaks: the break location), ``critical`` and
        ``reject`` (level -> bool).
    """
    x = np.asarray(series, dtype=np.float64)
    if x.size < MIN_POINTS:
        raise ValueError(f"the CUSUM test needs at least {MIN_POINTS} points")
    centred = x - x.mean()
    partial = np.cumsum(centred)
    stat = float(np.max(np.abs(partial)) / math.sqrt(prewhitened_lrv(centred) * x.size))
    return {
        "stat": stat, "index": int(np.argmax(np.abs(partial))) + 1, "critical": dict(CUSUM_CRITICAL),
        "reject": {k: stat > v for k, v in CUSUM_CRITICAL.items()},
    }


def _split_scan(x: np.ndarray) -> tuple[int, float]:
    """Split point (first index of the right segment) that minimises the sum of squared deviations, and its SSR."""
    n = x.size
    lo, hi = max(2, int(TRIM * n)), n - max(2, int(TRIM * n))
    csum, csq = np.cumsum(x), np.cumsum(x * x)
    k = np.arange(lo, hi + 1)
    left = csq[k - 1] - csum[k - 1] ** 2 / k
    right = (csq[-1] - csq[k - 1]) - (csum[-1] - csum[k - 1]) ** 2 / (n - k)
    best = int(np.argmin(left + right))
    return int(k[best]), float((left + right)[best])


def _wald_at(x: np.ndarray, k: int) -> tuple[float, float]:
    """Wald statistic and mean shift of a mean break at ``k``; the long-run variance uses the segment residuals."""
    left, right = x[:k], x[k:]
    resid = np.concatenate([left - left.mean(), right - right.mean()])
    omega = prewhitened_lrv(resid)
    shift = float(right.mean() - left.mean())
    return shift * shift / (omega * (1.0 / left.size + 1.0 / right.size)), shift


def sup_wald_test(series: np.ndarray) -> dict[str, Any]:
    """Sup-Wald (Quandt-Andrews) test for one mean break at an unknown date.

    Returns:
        ``stat``, ``index`` (first bar of the new regime), ``shift`` (new mean minus old, in the units of the series),
        ``shift_sd`` (the shift in standard deviations of the within-regime residual), ``critical`` and ``reject``.
    """
    x = np.asarray(series, dtype=np.float64)
    if x.size < MIN_POINTS:
        raise ValueError(f"the sup-Wald test needs at least {MIN_POINTS} points")
    k, _ = _split_scan(x)
    stat, shift = _wald_at(x, k)
    resid = np.concatenate([x[:k] - x[:k].mean(), x[k:] - x[k:].mean()])
    sd = float(resid.std(ddof=1)) or 1e-300
    return {
        "stat": stat, "index": k, "shift": shift, "shift_sd": abs(shift) / sd, "critical": dict(SUPW_CRITICAL),
        "reject": {lvl: stat > cv for lvl, cv in SUPW_CRITICAL.items()},
    }


def chow_test(series: np.ndarray, index: int) -> dict[str, Any]:
    """Chow test of a mean shift at a known bar ``index`` (first bar of the new regime), as a Wald statistic.

    Only for stationary series (a spread, a return): with trending levels the chi-square limit does not hold.
    """
    x = np.asarray(series, dtype=np.float64)
    if x.size < MIN_POINTS:
        raise ValueError(f"the Chow test needs at least {MIN_POINTS} points")
    if not 5 <= index <= x.size - 5:
        raise ValueError("the break date must leave at least 5 bars on each side")
    stat, shift = _wald_at(x, int(index))
    return {"stat": stat, "index": int(index), "shift": shift, "critical": dict(CHOW_CRITICAL), "reject": {k: stat > v for k, v in CHOW_CRITICAL.items()}}


def break_onset(series: np.ndarray, index: int, *, sigmas: float = 3.5, max_gap: int = 25) -> int:
    """Move a detected break date back to the bar where the series first left its early range.

    A step fitted to a series that drifts after the break lands in the middle of the drift. This walks back from
    ``index`` over the bars that lie more than ``sigmas`` standard deviations of the early sample (the first quarter, at
    most up to half-way to ``index``) from its mean, tolerating runs of up to ``max_gap`` bars inside the range, and
    returns the first such bar (or ``index`` when none lies outside).
    """
    x = np.asarray(series, dtype=np.float64)
    ref = x[: max(20, min(x.size // 4, index // 2))]
    outside = np.abs(x - ref.mean()) > sigmas * max(float(ref.std(ddof=1)), 1e-300)
    onset, misses, t = int(index), 0, int(index) - 1
    while t >= ref.size and misses <= max_gap:
        if outside[t]:
            onset, misses = t, 0
        else:
            misses += 1
        t -= 1
    return onset


def bai_perron_means(series: np.ndarray, *, max_breaks: int = 3, level: float = 0.05) -> dict[str, Any]:
    """Simplified Bai-Perron: sequential search for up to ``max_breaks`` mean breaks.

    Each round splits the segment whose best single break has the largest Wald statistic, as long as it exceeds the
    sequential critical value for the current number of breaks.

    Returns:
        ``breaks`` (sorted bar indices, first bar of each new regime), ``stats`` (the accepted statistics) and ``level``.
    """
    if level not in SEQ_CRITICAL:
        raise ValueError("level must be 0.05 or 0.01")
    x = np.asarray(series, dtype=np.float64)
    if x.size < MIN_POINTS:
        raise ValueError(f"the Bai-Perron search needs at least {MIN_POINTS} points")
    cuts = [0, x.size]
    breaks: list[int] = []
    stats: list[float] = []
    for found in range(min(max_breaks, len(SEQ_CRITICAL[level]))):
        best: tuple[float, int] | None = None
        for a, b in zip(cuts[:-1], cuts[1:], strict=True):
            if b - a < MIN_POINTS // 2:
                continue
            k, _ = _split_scan(x[a:b])
            stat, _ = _wald_at(x[a:b], k)
            if best is None or stat > best[0]:
                best = (stat, a + k)
        if best is None or best[0] <= SEQ_CRITICAL[level][found]:
            break
        breaks.append(best[1])
        stats.append(float(best[0]))
        cuts = sorted(cuts + [best[1]])
    return {"breaks": sorted(breaks), "stats": stats, "level": level}


__all__ = [
    "CHOW_CRITICAL", "CUSUM_CRITICAL", "SEQ_CRITICAL", "SUPW_CRITICAL", "bai_perron_means", "break_onset", "chow_test", "cusum_test",
    "prewhitened_lrv", "sup_wald_test",
]
