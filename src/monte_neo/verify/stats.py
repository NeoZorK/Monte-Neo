"""Selection-aware Sharpe statistics (PSR / Deflated Sharpe).

References: Bailey & Lopez de Prado, "The Sharpe Ratio Efficient Frontier" (2012)
and "The Deflated Sharpe Ratio" (2014). All Sharpe values here are *per bar*
(not annualized) so they match the sample length ``T`` used in the formulas.
"""

from __future__ import annotations

import math
import warnings
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

_EULER_GAMMA = 0.5772156649015329
_NORMAL = NormalDist()


def bar_returns(equity: np.ndarray, *, start: int = 0) -> np.ndarray:
    """Simple per-bar returns of an equity curve from ``start`` onward."""
    eq = np.asarray(equity, dtype=np.float64)[max(0, int(start)) :]
    if eq.size < 2:
        return np.zeros(0, dtype=np.float64)
    prev = eq[:-1]
    safe = np.where(prev > 0.0, prev, np.nan)
    rets = eq[1:] / safe - 1.0
    return np.nan_to_num(rets, nan=0.0, posinf=0.0, neginf=0.0)


def sharpe_per_bar(rets: np.ndarray) -> float:
    """Mean / std of per-bar returns (0.0 when degenerate)."""
    r = np.asarray(rets, dtype=np.float64)
    if r.size < 2:
        return 0.0
    sd = float(np.std(r, ddof=1))
    if not np.isfinite(sd) or sd <= 0.0:
        return 0.0
    return float(np.mean(r) / sd)


def _moments(r: np.ndarray) -> tuple[float, float]:
    """Skewness and (non-excess) kurtosis; normal fallback when degenerate."""
    sd = float(np.std(r))
    if r.size < 3 or sd <= 0.0:
        return 0.0, 3.0
    z = (r - float(np.mean(r))) / sd
    return float(np.mean(z**3)), float(np.mean(z**4))


def probabilistic_sharpe(
    sr: float, n_obs: int, skew: float = 0.0, kurt: float = 3.0, sr_benchmark: float = 0.0
) -> float:
    """PSR: probability that the true Sharpe exceeds ``sr_benchmark``."""
    if n_obs < 2:
        return 0.0
    denom_sq = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr
    if denom_sq <= 0.0:
        denom_sq = 1e-12
    z = (sr - sr_benchmark) * math.sqrt(n_obs - 1) / math.sqrt(denom_sq)
    return float(_NORMAL.cdf(z))


def expected_max_sharpe(n_trials: int, sr_variance: float) -> float:
    """Expected maximum Sharpe among ``n_trials`` zero-skill trials."""
    n = int(n_trials)
    if n <= 1 or sr_variance <= 0.0:
        return 0.0
    a = _NORMAL.inv_cdf(1.0 - 1.0 / n)
    b = _NORMAL.inv_cdf(1.0 - 1.0 / (n * math.e))
    return float(math.sqrt(sr_variance) * ((1.0 - _EULER_GAMMA) * a + _EULER_GAMMA * b))


def deflated_sharpe(
    rets: np.ndarray,
    *,
    n_trials: int = 1,
    trial_sharpes: np.ndarray | None = None,
    periods_per_year: float = 252.0,
) -> dict[str, Any]:
    """Deflated Sharpe report for one selected strategy.

    ``n_trials`` is how many variants were tried before this one was chosen.
    Without ``trial_sharpes`` the null sampling variance ``1/(T-1)`` is used.
    """
    r = np.asarray(rets, dtype=np.float64)
    t = int(r.size)
    sr = sharpe_per_bar(r)
    skew, kurt = _moments(r)
    n = max(1, int(n_trials))
    if trial_sharpes is not None and np.asarray(trial_sharpes).size >= 2:
        sr_var = float(np.var(np.asarray(trial_sharpes, dtype=np.float64), ddof=1))
        variance_source = "trial_sharpes"
    else:
        sr_var = 1.0 / max(1, t - 1)
        variance_source = "null_sampling_variance"
    sr0 = expected_max_sharpe(n, sr_var)
    return {
        "n_obs": t,
        "n_trials": n,
        "sharpe_per_bar": sr,
        "sharpe_annualized": float(sr * math.sqrt(max(periods_per_year, 1.0))),
        "periods_per_year": float(periods_per_year),
        "skew": skew,
        "kurtosis": kurt,
        "psr": probabilistic_sharpe(sr, t, skew, kurt, 0.0),
        "expected_max_sharpe_per_bar": sr0,
        "deflated_sharpe": probabilistic_sharpe(sr, t, skew, kurt, sr0),
        "sr_variance_source": variance_source,
    }


def infer_periods_per_year(timestamps: Any, default: float = 252.0) -> float:
    """Bars per calendar year from timestamps (24/7 calendar); ``default`` if unknown."""
    if timestamps is None:
        return default
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parsed = pd.to_datetime(pd.Series(np.asarray(timestamps)), utc=True, errors="coerce").dropna()
    if len(parsed) < 3:
        return default
    ts = parsed.to_numpy(dtype="datetime64[ns]").astype(np.int64)
    step_ns = float(np.median(np.diff(ts)))
    if not np.isfinite(step_ns) or step_ns <= 0.0:
        return default
    return float(365.25 * 86_400e9 / step_ns)


__all__ = [
    "bar_returns",
    "deflated_sharpe",
    "expected_max_sharpe",
    "infer_periods_per_year",
    "probabilistic_sharpe",
    "sharpe_per_bar",
]
