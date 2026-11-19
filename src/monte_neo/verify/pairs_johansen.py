"""Johansen cointegration rank test for 3 to 5 series (plain numpy).

Source: Johansen (1988, 1991). Model: a VAR in levels with ``k_diff`` lagged differences and an unrestricted constant
(Osterwald-Lenum / MacKinnon-Haug-Michelis case "constant in the data", statsmodels ``det_order=0``). The critical values
are those of MacKinnon, Haug & Michelis (1999) for ``n - r`` common trends (1 to 5), 90 / 95 / 99 %; the 95 % trace value
for one trend, 3.8415, is the chi-square(1) quantile and the two-trend value 15.4947 is the one printed in every
textbook table.
"""

from __future__ import annotations

from typing import Any

import numpy as np

# (n - r) -> (90 %, 95 %, 99 %)
TRACE_CRITICAL = {
    1: (2.7055, 3.8415, 6.6349), 2: (13.4294, 15.4947, 19.9371), 3: (27.0669, 29.7961, 35.4628),
    4: (44.4929, 47.8545, 54.6815), 5: (65.8202, 69.8189, 76.0707),
}
MAXEIG_CRITICAL = {
    1: (2.7055, 3.8415, 6.6349), 2: (12.2971, 14.2639, 18.5200), 3: (18.8928, 21.1316, 25.8650),
    4: (25.1236, 27.5858, 32.7172), 5: (31.2379, 33.8769, 39.3693),
}
_LEVELS = {"90": 0, "95": 1, "99": 2}


def _residuals(y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Residuals of ``y`` regressed on ``z`` (column-wise)."""
    coef, *_ = np.linalg.lstsq(z, y, rcond=None)
    return y - z @ coef


def johansen(levels: np.ndarray, *, k_diff: int = 1, level: str = "95") -> dict[str, Any]:
    """Johansen trace and maximum-eigenvalue tests; the rank is chosen by the sequential trace test.

    Args:
        levels: Array ``(bars, n)`` of (log) price levels, ``2 <= n <= 5``.
        k_diff: Lagged differences in the VECM (VAR order minus one).
        level: ``"90"``, ``"95"`` or ``"99"``.

    Returns:
        ``rank`` (number of cointegrating relations), ``eigenvalues``, ``trace``, ``max_eig`` and their critical values
        per hypothesis ``r = 0, 1, ...``, ``vector`` (the first cointegrating vector scaled so its first entry is 1:
        a hedge ratio for each series) and ``n_obs``.
    """
    y = np.asarray(levels, dtype=np.float64)
    if y.ndim != 2 or not 2 <= y.shape[1] <= 5:
        raise ValueError("Johansen needs a table of 2 to 5 series")
    if level not in _LEVELS:
        raise ValueError("level must be '90', '95' or '99'")
    n = y.shape[1]
    dy = np.diff(y, axis=0)
    t = dy.shape[0] - k_diff
    if t < 10 * n:
        raise ValueError("too few bars for the Johansen test")
    lagged = [dy[k_diff - i : dy.shape[0] - i] for i in range(1, k_diff + 1)]
    z = np.column_stack([np.ones(t)] + lagged)
    r0 = _residuals(dy[k_diff:], z)
    r1 = _residuals(y[k_diff:-1], z)
    s00, s11, s01 = r0.T @ r0 / t, r1.T @ r1 / t, r0.T @ r1 / t
    vals, vecs = np.linalg.eig(np.linalg.solve(s11, s01.T @ np.linalg.solve(s00, s01)))
    order = np.argsort(-vals.real)
    lam = np.clip(vals.real[order], 0.0, 1.0 - 1e-12)
    vec = vecs.real[:, order]
    log_term = -np.log1p(-lam)
    trace = np.array([t * log_term[r:].sum() for r in range(n)])
    max_eig = t * log_term
    col = _LEVELS[level]
    crit_tr = np.array([TRACE_CRITICAL[n - r][col] for r in range(n)])
    crit_me = np.array([MAXEIG_CRITICAL[n - r][col] for r in range(n)])
    rank = 0
    while rank < n and trace[rank] > crit_tr[rank]:
        rank += 1
    first = vec[:, 0] / vec[0, 0] if abs(vec[0, 0]) > 1e-12 else vec[:, 0]
    return {
        "rank": int(rank), "level": level, "n_obs": int(t), "eigenvalues": lam, "trace": trace, "trace_critical": crit_tr,
        "max_eig": max_eig, "max_eig_critical": crit_me, "vector": first,
    }


__all__ = ["MAXEIG_CRITICAL", "TRACE_CRITICAL", "johansen"]
