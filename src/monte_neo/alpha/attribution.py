"""Family B: is the return alpha or a known factor? Exposure, residual alpha, spanning, run entry point."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.alpha._core import newey_west_t
from monte_neo.alpha.attribution_ols import nw_lag, ols_hac
from monte_neo.alpha.attribution_tail import (
    check_crowding,
    check_hidden_short_vol,
    check_known_anomaly,
    check_market_timing,
)
from monte_neo.verify.checks import check

MIN_ROWS = 60
HLZ_HURDLE = 3.0
SPAN_MIN_GAIN = 0.05
RIDGE = 1e-6

NEXT_ACTIONS: dict[str, str] = {
    "factor_exposure": "Read the betas: the largest |t| factors are what the strategy really trades.",
    "residual_alpha": "Neutralise the signal to momentum and market, then re-test the residual alpha.",
    "factor_spanning": "If the factors already span the strategy, trade the factors directly (cheaper) or find a new signal.",
    "hidden_short_volatility": "Stress the strategy in the worst market bars; size for the crash, not for the average day.",
    "market_timing_beta": "Check whether beta changes with the market regime; hedge the market exposure out.",
    "crowding": "Reduce overlap with momentum and low-vol, or cap exposure when those factors crash.",
    "known_anomaly_match": "Compare against the closest factor: if the correlation is high, test the strategy net of it.",
}


def skip(check_id: str, n: int) -> dict[str, Any]:
    """Skip row for too few aligned observations."""
    return check(check_id, "statistics", "skip", f"only {n} aligned rows (need {MIN_ROWS})", {"n": n})


def check_factor_exposure(r: np.ndarray, f: pd.DataFrame) -> dict[str, Any]:
    """B1: OLS of strategy returns on the factors with HAC t-stats."""
    if len(r) < MIN_ROWS:
        return skip("factor_exposure", len(r))
    fit = ols_hac(r, f.to_numpy())
    names = list(f.columns)
    betas = {k: round(float(b), 4) for k, b in zip(names, fit["beta"][1:])}
    tstat = {k: round(float(t), 2) for k, t in zip(names, fit["t"][1:])}
    top = sorted(names, key=lambda k: -abs(tstat[k]))[:2]
    summary = f"factors explain {fit['r2']:.0%} of return variance; strongest: " + ", ".join(
        f"{k} (beta {betas[k]:+.2f}, t {tstat[k]:+.1f})" for k in top
    )
    return check(
        "factor_exposure", "statistics", "info", summary, {"betas": betas, "t_stats": tstat, "r2": round(float(fit["r2"]), 4)}
    )


def check_residual_alpha(r: np.ndarray, f: pd.DataFrame, ppy: float) -> dict[str, Any]:
    """B2: annualised intercept and its HAC t-stat; flags repackaged factors."""
    n = len(r)
    if n < MIN_ROWS:
        return skip("residual_alpha", n)
    fit = ols_hac(r, f.to_numpy())
    a, ta, r2 = float(fit["beta"][0]), float(fit["t"][0]), float(fit["r2"])
    mean, _, t_raw = newey_west_t(r, nw_lag(n))
    contrib = {k: float(b) * float(f[k].mean()) for k, b in zip(f.columns, fit["beta"][1:])}
    explained = float(np.clip(1.0 - a / mean, 0.0, 1.0)) if mean > 0 else 0.0
    names = [k for k, v in sorted(contrib.items(), key=lambda kv: -abs(kv[1]))[:2] if abs(v) > 0]
    details = {
        "alpha_annual": round(a * ppy, 6),
        "alpha_t": round(ta, 2),
        "raw_mean_annual": round(mean * ppy, 6),
        "raw_t": round(t_raw, 2),
        "r2": round(r2, 4),
        "explained_return_share": round(explained, 4),
    }
    if abs(t_raw) >= 2 and ta < 2 and r2 >= 0.3:
        who = " and ".join(names) if names else "the factors"
        msg = f"{explained:.0%} of the return is explained by {who}: repackaged factors (alpha t {ta:.1f})"
        return check("residual_alpha", "statistics", "fail", msg, details)
    if ta >= HLZ_HURDLE:
        return check("residual_alpha", "statistics", "pass", f"residual alpha t {ta:.1f} clears the 3.0 hurdle", details)
    if ta >= 2.0:
        msg = f"residual alpha t {ta:.1f} is below the Harvey-Liu-Zhu hurdle of 3.0"
        return check("residual_alpha", "statistics", "warn", msg, details)
    return check("residual_alpha", "statistics", "warn", f"no significant residual alpha (t {ta:.1f})", details)


def _max_sharpe(x: np.ndarray, ppy: float) -> float:
    mu = x.mean(axis=0)
    cov = np.atleast_2d(np.cov(x, rowvar=False))
    cov = cov + RIDGE * float(np.mean(np.diag(cov))) * np.eye(cov.shape[0])
    return float(np.sqrt(max(mu @ np.linalg.solve(cov, mu), 0.0) * ppy))


def check_factor_spanning(r: np.ndarray, f: pd.DataFrame, ppy: float) -> dict[str, Any]:
    """B4: increase of the factors' tangency Sharpe when the strategy is added."""
    if len(r) < MIN_ROWS:
        return skip("factor_spanning", len(r))
    base = _max_sharpe(f.to_numpy(), ppy)
    full = _max_sharpe(np.column_stack([f.to_numpy(), r]), ppy)
    gain = full - base
    details = {"sharpe_factors": round(base, 3), "sharpe_with_strategy": round(full, 3), "increase": round(gain, 3)}
    if gain < SPAN_MIN_GAIN:
        msg = f"adds nothing the factors do not have (max Sharpe {base:.2f} -> {full:.2f})"
        return check("factor_spanning", "statistics", "warn", msg, details)
    return check("factor_spanning", "statistics", "info", f"max Sharpe rises {base:.2f} -> {full:.2f} (+{gain:.2f})", details)


def run_attribution(r: np.ndarray, factors: pd.DataFrame, periods_per_year: float) -> list[dict[str, Any]]:
    """Run all family B checks.

    Args:
        r: Strategy returns per bar, shape (T,), aligned row by row with ``factors``.
        factors: Factor returns (T x K), as made by ``build_factors`` or ``load_factors``.
        periods_per_year: Bars per year, for annualisation.

    Returns:
        Check rows (B1, B2, B4, B5, B6, B7, B8) in that order.
    """
    r = np.asarray(r, dtype=np.float64)
    f = pd.DataFrame(factors).reset_index(drop=True)
    f = f.loc[:, f.notna().sum() >= MIN_ROWS]
    ok = np.isfinite(r) & f.notna().all(axis=1).to_numpy() if f.shape[1] else np.isfinite(r)
    r, f = r[ok], f[ok].reset_index(drop=True)
    if f.shape[1] == 0:
        return [skip(i, len(r)) for i in NEXT_ACTIONS]
    return [
        check_factor_exposure(r, f),
        check_residual_alpha(r, f, periods_per_year),
        check_factor_spanning(r, f, periods_per_year),
        check_hidden_short_vol(r, f),
        check_market_timing(r, f),
        check_crowding(r, f),
        check_known_anomaly(r, f),
    ]
