"""OLS with Newey-West (HAC) standard errors, in plain numpy."""

from __future__ import annotations

import numpy as np


def nw_lag(n: int) -> int:
    """Newey-West rule-of-thumb bandwidth ``floor(4 * (n / 100) ** (2 / 9))``."""
    return max(1, int(4.0 * (max(n, 1) / 100.0) ** (2.0 / 9.0)))


def ols_hac(y: np.ndarray, x: np.ndarray, *, add_const: bool = True) -> dict[str, object]:
    """Regress ``y`` on ``x`` with Bartlett-kernel HAC t-statistics.

    Args:
        y: Dependent variable, shape (T,).
        x: Regressors, shape (T, K) or (T,).
        add_const: Prepend an intercept column (it becomes ``beta[0]``).

    Returns:
        Dict with ``beta``, ``t``, ``r2``, ``resid`` and ``n``. Rank-deficient designs use a pseudo-inverse.
    """
    y = np.asarray(y, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if add_const:
        x = np.column_stack([np.ones(len(y)), x])
    n = len(y)
    xtx_inv = np.linalg.pinv(x.T @ x)
    beta = xtx_inv @ (x.T @ y)
    u = y - x @ beta
    z = x * u[:, None]
    s = z.T @ z
    lag = min(nw_lag(n), n - 2)
    for k in range(1, lag + 1):
        g = z[k:].T @ z[:-k]
        s += (1.0 - k / (lag + 1.0)) * (g + g.T)
    cov = xtx_inv @ s @ xtx_inv
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(se > 0, beta / se, np.nan)
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float(u @ u) / tss if tss > 0 else 0.0
    return {"beta": beta, "t": t, "r2": max(0.0, r2), "resid": u, "n": n}
