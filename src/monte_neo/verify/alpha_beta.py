"""Alpha after beta: split a strategy's return into market exposure and the part the market does not explain.

A long-biased strategy on a rising market earns beta, not alpha: regressing it on buy-and-hold shows how much of the
return is the market's. The regression is ``r_t = alpha + beta * b_t + e_t`` by least squares with Newey-West (1987)
heteroskedasticity- and autocorrelation-consistent errors (Bartlett kernel, ``floor(4 (n/100)^(2/9))`` lags); the 95 %
interval of alpha is ``alpha +- 1.96 se``. The gate asks whether that interval excludes zero on the positive side.

Sources: Newey and West (1987), Econometrica 55(3); Sharpe (1964) for the market model; Jensen (1968) for alpha.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from monte_neo.verify.checks import check

MIN_OBS = 30
Z95 = 1.959964
T_MIN = 2.0


def nw_regression(y: np.ndarray, x: np.ndarray) -> dict[str, float]:
    """OLS of ``y`` on a constant and ``x`` with Newey-West standard errors: alpha, beta, their errors, R squared."""
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
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {
        "alpha": float(coef[0]), "beta": float(coef[1]),
        "alpha_se": math.sqrt(max(float(cov[0, 0]), 1e-30)), "beta_se": math.sqrt(max(float(cov[1, 1]), 1e-30)),
        "r2": float(1.0 - float(e @ e) / ss_tot) if ss_tot > 0 else 0.0, "lags": lags,
    }


def alpha_beta(r: np.ndarray, bench: np.ndarray, periods_per_year: float) -> dict[str, Any]:
    """Decompose ``r`` on ``bench``: annual alpha with 95 % interval, beta, share of the return that is beta.

    ``beta_share`` is ``beta * mean(bench) / mean(r)`` (how much of the average return the market exposure explains);
    it is ``None`` when the mean return is zero or negative.
    """
    reg = nw_regression(r, bench)
    ppy = float(periods_per_year)
    a, se = reg["alpha"], reg["alpha_se"]
    mean_r = float(r.mean())
    return {
        "n": int(r.size), "beta": reg["beta"], "beta_se": reg["beta_se"], "r2": reg["r2"], "lags": reg["lags"],
        "alpha_annual": a * ppy, "alpha_ci95_annual": [(a - Z95 * se) * ppy, (a + Z95 * se) * ppy],
        "alpha_t": a / se, "beta_share": float(reg["beta"] * bench.mean() / mean_r) if mean_r > 0 else None,
    }


def alpha_after_beta_row(r: np.ndarray, bench: np.ndarray, periods_per_year: float) -> dict[str, Any]:
    """Gate: after removing the benchmark's exposure, is the alpha significantly positive?

    ``pass`` when the 95 % interval of annual alpha lies above zero (t >= 2); ``warn`` otherwise (the return is not
    shown to be more than market exposure); ``skip`` for too few bars or a constant benchmark.
    """
    n = min(r.size, bench.size)
    r, bench = np.asarray(r[-n:], dtype=np.float64), np.asarray(bench[-n:], dtype=np.float64)
    if n < MIN_OBS:
        return check("alpha_after_beta", "statistics", "skip", f"only {n} bars: too few to separate alpha from beta")
    if float(np.std(bench)) <= 0.0 or float(np.std(r)) <= 0.0:
        return check("alpha_after_beta", "statistics", "skip", "the strategy or the benchmark has no variation")
    d = alpha_beta(r, bench, periods_per_year)
    lo, hi = d["alpha_ci95_annual"]
    share = f", {d['beta_share']:.0%} of the average return is market exposure" if d["beta_share"] is not None else ""
    text = (f"beta {d['beta']:.2f} to buy & hold, annual alpha {d['alpha_annual']:+.1%} "
            f"(95% interval {lo:+.1%} to {hi:+.1%}, t={d['alpha_t']:.1f}){share}")
    if d["alpha_t"] >= T_MIN and lo > 0:
        return check("alpha_after_beta", "statistics", "pass", text, d)
    return check("alpha_after_beta", "statistics", "warn", "alpha is not significant after beta: " + text, d)


__all__ = ["MIN_OBS", "T_MIN", "alpha_after_beta_row", "alpha_beta", "nw_regression"]
