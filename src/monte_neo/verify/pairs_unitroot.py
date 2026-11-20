"""Unit-root and cointegration tests on a pair's spread, in plain numpy (no statsmodels, no scipy).

Implemented tests and their sources:

* **ADF** (Dickey & Fuller 1979; Said & Dickey 1984) with a constant and AIC lag selection; the approximate p-value is
  the MacKinnon (1994) response surface for one series with a constant (the same polynomial statsmodels ships).
  Check: the asymptotic 5 % critical value -2.8621 gives p = 0.0500.
* **Engle-Granger** (Engle & Granger 1987): ADF on the residual of ``y = a + b x``. The residual is estimated, so the
  ordinary ADF table is wrong; the 1 / 5 / 10 % critical values are the asymptotic MacKinnon (2010) values for two
  series with a constant: -3.8964, -3.3361, -3.0444.
* **KPSS** (Kwiatkowski, Phillips, Schmidt & Shin 1992), level stationarity, Bartlett kernel; critical values 0.739 /
  0.463 / 0.347 (1 / 5 / 10 %) from their Table 1.
* **Half-life** of mean reversion from the AR(1) form of the Ornstein-Uhlenbeck process (Uhlenbeck & Ornstein 1930;
  ``ln 2 / -ln(1 + b)`` for ``ds = a + b s dt + e``).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

EG_CRITICAL = {0.01: -3.89644, 0.05: -3.33613, 0.10: -3.04445}
KPSS_CRITICAL = {0.01: 0.739, 0.05: 0.463, 0.10: 0.347}
_TAU_MAX, _TAU_MIN, _TAU_STAR = 2.74, -18.83, -1.61
_SMALL_P = (2.1659, 1.4412, 0.038269)
_LARGE_P = (1.7339, 0.93202, -0.12745, -0.010368)


def _ols(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Least squares: coefficients, residuals and the coefficient covariance matrix."""
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    dof = max(1, y.size - x.shape[1])
    sigma2 = float(resid @ resid) / dof
    return beta, resid, sigma2 * np.linalg.pinv(x.T @ x)


def normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def adf_pvalue(tau: float) -> float:
    """Approximate p-value of an ADF statistic (constant, one series): MacKinnon (1994) response surface."""
    if tau > _TAU_MAX:
        return 1.0
    if tau < _TAU_MIN:
        return 0.0
    coef = _SMALL_P if tau <= _TAU_STAR else _LARGE_P
    return normal_cdf(sum(c * tau**i for i, c in enumerate(coef)))


def _design(y: np.ndarray, lag: int, start: int) -> tuple[np.ndarray, np.ndarray]:
    """ADF regression ``dy_t = c + g y_{t-1} + sum phi_i dy_{t-i}`` for ``t >= start`` (column 0 is ``y_{t-1}``)."""
    dy = np.diff(y)
    dep = dy[start:]
    cols = [y[start:-1]] + [dy[start - i : dy.size - i] for i in range(1, lag + 1)] + [np.ones(dep.size)]
    return dep, np.column_stack(cols)


def adf_test(series: np.ndarray, *, max_lag: int | None = None) -> dict[str, Any]:
    """Augmented Dickey-Fuller test (constant) with the lag chosen by AIC.

    Args:
        series: The series to test, at least 20 points.
        max_lag: Largest lag of differences; default Schwert's ``int(12 (n / 100) ** 0.25)``.

    Returns:
        ``stat`` (the t-statistic of the lagged level), ``lag``, ``n_obs`` and ``pvalue`` (MacKinnon 1994, valid for a
        series that was not estimated; for a regression residual use :func:`engle_granger`).
    """
    y = np.asarray(series, dtype=np.float64)
    if y.size < 20:
        raise ValueError("the ADF test needs at least 20 points")
    top = int(12.0 * (y.size / 100.0) ** 0.25) if max_lag is None else int(max_lag)
    top = max(0, min(top, y.size // 4))
    best, best_aic = 0, math.inf
    for lag in range(top + 1):
        dep, x = _design(y, lag, top)
        _, resid, _ = _ols(dep, x)
        aic = dep.size * math.log(max(float(resid @ resid) / dep.size, 1e-300)) + 2 * x.shape[1]
        if aic < best_aic:
            best, best_aic = lag, aic
    dep, x = _design(y, best, best)
    beta, _, cov = _ols(dep, x)
    stat = float(beta[0] / math.sqrt(max(cov[0, 0], 1e-300)))
    return {"stat": stat, "lag": int(best), "n_obs": int(dep.size), "pvalue": adf_pvalue(stat)}


def engle_granger(log_y: np.ndarray, log_x: np.ndarray) -> dict[str, Any]:
    """Engle-Granger two-step test: regress ``y`` on ``x``, then test the residual for a unit root.

    Returns:
        ``alpha``, ``beta`` (the hedge ratio), ``spread`` (the residual), ``stat``, ``lag``, ``critical`` (1/5/10 %),
        ``reject`` (level -> bool) and ``pvalue_bucket`` (``"<0.01"``, ``"0.01-0.05"``, ``"0.05-0.10"`` or ``">0.10"``).
        The p-value is not given as a number: the critical values come from MacKinnon's response surface for the
        asymptotic case and are exact only for long samples.
    """
    y, x = np.asarray(log_y, dtype=np.float64), np.asarray(log_x, dtype=np.float64)
    if y.size != x.size:
        raise ValueError("the two series must have the same length")
    (alpha, beta), spread, _ = _ols(y, np.column_stack([np.ones(y.size), x]))
    adf = adf_test(spread)
    reject = {lvl: adf["stat"] < cv for lvl, cv in EG_CRITICAL.items()}
    bucket = "<0.01" if reject[0.01] else "0.01-0.05" if reject[0.05] else "0.05-0.10" if reject[0.10] else ">0.10"
    return {
        "alpha": float(alpha), "beta": float(beta), "spread": spread, "stat": adf["stat"], "lag": adf["lag"],
        "critical": dict(EG_CRITICAL), "reject": reject, "pvalue_bucket": bucket,
    }


def long_run_variance(x: np.ndarray, lags: int) -> float:
    """Newey-West (Bartlett kernel) long-run variance of ``x`` around its mean."""
    e = np.asarray(x, dtype=np.float64) - float(np.mean(x))
    n = e.size
    out = float(e @ e) / n
    for k in range(1, min(lags, n - 1) + 1):
        out += 2.0 * (1.0 - k / (lags + 1.0)) * float(e[k:] @ e[:-k]) / n
    return out


def kpss_test(series: np.ndarray, *, lags: int | None = None) -> dict[str, Any]:
    """KPSS test of level stationarity (the null is that the series is stationary).

    Args:
        series: The series to test.
        lags: Bartlett bandwidth; default ``int(12 (n / 100) ** 0.25)``.

    Returns:
        ``stat``, ``lags``, ``critical`` (1/5/10 %) and ``reject`` (level -> bool, True = stationarity rejected).
    """
    y = np.asarray(series, dtype=np.float64)
    n = y.size
    if n < 20:
        raise ValueError("the KPSS test needs at least 20 points")
    bandwidth = int(12.0 * (n / 100.0) ** 0.25) if lags is None else int(lags)
    partial = np.cumsum(y - y.mean())
    omega = max(long_run_variance(y, bandwidth), 1e-300)
    stat = float(partial @ partial) / (n * n * omega)
    return {"stat": stat, "lags": bandwidth, "critical": dict(KPSS_CRITICAL), "reject": {k: stat > v for k, v in KPSS_CRITICAL.items()}}


def half_life(spread: np.ndarray) -> dict[str, Any]:
    """Half-life of mean reversion in bars from ``ds_t = a + b s_{t-1} + e``.

    Returns:
        ``b`` (the mean-reversion coefficient), ``half_life`` in bars (``inf`` when ``b >= 0`` or ``b <= -1``, i.e. the
        spread does not revert or overshoots) and ``mean_reverting``.
    """
    s = np.asarray(spread, dtype=np.float64)
    if s.size < 20:
        raise ValueError("the half-life needs at least 20 points")
    beta, _, _ = _ols(np.diff(s), np.column_stack([np.ones(s.size - 1), s[:-1]]))
    b = float(beta[1])
    ok = -1.0 < b < 0.0
    return {"b": b, "half_life": float(-math.log(2.0) / math.log1p(b)) if ok else math.inf, "mean_reverting": ok}


__all__ = [
    "EG_CRITICAL", "KPSS_CRITICAL", "adf_pvalue", "adf_test", "engle_granger", "half_life", "kpss_test",
    "long_run_variance", "normal_cdf",
]
