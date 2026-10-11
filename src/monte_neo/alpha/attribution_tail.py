"""Family B tail-risk and similarity checks: hidden short volatility, timing, crowding, closest anomaly."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.alpha.attribution_ols import ols_hac
from monte_neo.verify.checks import check

MIN_ROWS = 60


def _skip(check_id: str, n: int) -> dict[str, Any]:
    return check(check_id, "statistics", "skip", f"only {n} aligned rows (need {MIN_ROWS})", {"n": n})


def _market(f: pd.DataFrame) -> np.ndarray:
    col = "market" if "market" in f.columns else f.columns[0]
    return f[col].to_numpy(dtype=np.float64)


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.std() <= 0 or b.std() <= 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def check_hidden_short_vol(r: np.ndarray, f: pd.DataFrame) -> dict[str, Any]:
    """B5: skew, kurtosis, Treynor-Mazuy gamma and loss concentration; flags selling insurance."""
    n = len(r)
    if n < MIN_ROWS:
        return _skip("hidden_short_volatility", n)
    mean, sd = float(r.mean()), float(r.std(ddof=1))
    z = (r - mean) / sd if sd > 0 else np.zeros(n)
    skew, kurt = float(np.mean(z**3)), float(np.mean(z**4) - 3.0)
    m = _market(f)
    fit = ols_hac(r, np.column_stack([m, m**2]))
    gamma, t_g = float(fit["beta"][2]), float(fit["t"][2])
    total = float(r.sum())
    k5 = max(1, int(np.ceil(0.05 * n)))
    k1 = max(1, int(np.ceil(0.01 * n)))
    lost_mkt5 = float(-r[np.argsort(m)[:k5]].sum() / total) if total > 0 else float("nan")
    lost_r1 = float(-r[np.argsort(r)[:k1]].sum() / total) if total > 0 else float("nan")
    details = {
        "skew": round(skew, 3),
        "excess_kurtosis": round(kurt, 3),
        "worst_bar": round(float(r.min()), 5),
        "worst_bar_in_std": round(float((r.min() - mean) / sd), 2) if sd > 0 else None,
        "tm_gamma": round(gamma, 4),
        "tm_gamma_t": round(t_g, 2),
        "profit_lost_in_market_worst_5pct": round(lost_mkt5, 3),
        "profit_lost_in_own_worst_1pct": round(lost_r1, 3),
    }
    gamma_bad = gamma < 0 and t_g <= -2
    shape_bad = skew < -1 and kurt > 3
    if gamma_bad and shape_bad and lost_r1 > 0.5:
        msg = "steady gains and rare crashes: the strategy sells insurance"
        return check("hidden_short_volatility", "statistics", "fail", msg, details)
    if gamma_bad or shape_bad:
        why = "negative convexity to the market" if gamma_bad else f"skew {skew:.1f}, excess kurtosis {kurt:.1f}"
        return check("hidden_short_volatility", "statistics", "warn", f"short-option payoff signs: {why}", details)
    return check("hidden_short_volatility", "statistics", "pass", f"no short-volatility payoff (skew {skew:.1f})", details)


def check_market_timing(r: np.ndarray, f: pd.DataFrame) -> dict[str, Any]:
    """B6: Henriksson-Merton up and down market beta."""
    n = len(r)
    if n < MIN_ROWS:
        return _skip("market_timing_beta", n)
    m = _market(f)
    fit = ols_hac(r, np.column_stack([m, np.maximum(0.0, -m)]))
    b, c, t_c = float(fit["beta"][1]), float(fit["beta"][2]), float(fit["t"][2])
    details = {"up_beta": round(b, 3), "down_beta": round(b - c, 3), "timing_coef": round(c, 3), "timing_t": round(t_c, 2)}
    return check("market_timing_beta", "statistics", "info", f"up beta {b:.2f}, down beta {b - c:.2f} (timing t {t_c:.1f})", details)


def check_crowding(r: np.ndarray, f: pd.DataFrame) -> dict[str, Any]:
    """B7: correlation with momentum and low_vol and the return on momentum crash days."""
    n = len(r)
    names = [c for c in ("momentum", "low_vol") if c in f.columns]
    if n < MIN_ROWS or not names:
        return _skip("crowding", n) if n < MIN_ROWS else check(
            "crowding", "statistics", "skip", "no momentum or low_vol factor", {}
        )
    details: dict[str, Any] = {f"corr_{k}": round(_corr(r, f[k].to_numpy()), 3) for k in names}
    if "momentum" in names:
        mom = f["momentum"].to_numpy()
        worst = np.argsort(mom)[: max(1, int(np.ceil(0.05 * n)))]
        details["mean_return_momentum_worst_5pct"] = round(float(r[worst].mean()), 6)
        details["mean_return_all"] = round(float(r.mean()), 6)
    msg = "correlation with " + ", ".join(f"{k} {details[f'corr_{k}']:+.2f}" for k in names)
    if "mean_return_momentum_worst_5pct" in details:
        msg += f"; mean return on momentum crash days {details['mean_return_momentum_worst_5pct']:+.4f}"
    return check("crowding", "statistics", "info", msg, details)


def check_known_anomaly(r: np.ndarray, f: pd.DataFrame) -> dict[str, Any]:
    """B8: the factor with the largest absolute correlation to the strategy."""
    if len(r) < MIN_ROWS:
        return _skip("known_anomaly_match", len(r))
    corr = {k: _corr(r, f[k].to_numpy()) for k in f.columns}
    best = max(corr, key=lambda k: abs(corr[k]))
    details = {"correlations": {k: round(v, 3) for k, v in corr.items()}, "closest": best}
    return check("known_anomaly_match", "statistics", "info", f"closest known factor: {best} (corr {corr[best]:+.2f})", details)
