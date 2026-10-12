"""Red-flag checks on a bare return series (allocator due diligence): smoothing, kinks, consistency, drawdown."""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any

import numpy as np

from monte_neo.verify.checks import check
from monte_neo.verify.stats import deflated_sharpe

_N = NormalDist()
SMOOTH_RHO = 0.2
SMOOTH_T = 2.0
KINK_Z = -2.0
KINK_MIN_COUNT = 8
CONSISTENCY_Z = 3.0
CONSISTENCY_SHARPE = 3.0
ROUND_FACTOR = 3.0
DSR_MIN = 0.95
DD_QUANTILE = 5.0
DD_SIMS = 500


def _acf(r: np.ndarray, k: int) -> float:
    c = r - r.mean()
    den = float(np.dot(c, c))
    return float(np.dot(c[k:], c[:-k]) / den) if den > 0 else 0.0


def smoothing_weights(r: np.ndarray) -> tuple[np.ndarray, float]:
    """MA(2) smoothing weights (theta0..2, >= 0, sum 1) by matching lag-1/2 autocorrelations on a 0.01 grid."""
    rho1, rho2 = _acf(r, 1), _acf(r, 2)
    g = np.arange(0, 101) / 100.0
    t0, t1 = np.meshgrid(g, g, indexing="ij")
    t2 = 1.0 - t0 - t1
    ok = t2 >= -1e-12
    s = t0**2 + t1**2 + t2**2
    err = (np.where(ok, (t0 * t1 + t1 * t2) / s, 9.0) - rho1) ** 2 + (np.where(ok, t0 * t2 / s, 9.0) - rho2) ** 2
    i, j = np.unravel_index(int(np.argmin(err)), err.shape)
    theta = np.array([t0[i, j], t1[i, j], max(t2[i, j], 0.0)])
    return theta, float(np.sum(theta**2))


def return_smoothing(r: np.ndarray, ppy: float) -> dict[str, Any]:
    """Getmansky-Lo-Makarov smoothing: lag-1 autocorrelation and the unsmoothed Sharpe."""
    n = r.size
    rho1 = _acf(r, 1)
    t_stat = rho1 * math.sqrt(n)
    theta, s2 = smoothing_weights(r)
    sd = float(np.std(r, ddof=1))
    naive = float(r.mean() / sd * math.sqrt(ppy)) if sd > 0 else 0.0
    unsm = naive * math.sqrt(s2)
    det = {"rho1": rho1, "t_stat": t_stat, "theta": [float(x) for x in theta], "sharpe": naive, "unsmoothed_sharpe": unsm}
    if rho1 > SMOOTH_RHO and abs(t_stat) >= SMOOTH_T:
        msg = (f"returns look smoothed (lag-1 autocorrelation {rho1:.2f}, t={t_stat:.1f}): illiquid marks or stale "
               f"pricing; the unsmoothed Sharpe is {unsm:.2f} (reported {naive:.2f})")
        return check("return_smoothing", "statistics", "warn", msg, det)
    return check("return_smoothing", "statistics", "pass",
                 f"no sign of smoothing (lag-1 autocorrelation {rho1:.2f}, unsmoothed Sharpe {unsm:.2f})", det)


def zero_kink(r: np.ndarray) -> dict[str, Any]:
    """Bollen-Pool discontinuity at zero: small losses vs small gains against a normal-model expectation."""
    mu, sd = float(r.mean()), float(np.std(r, ddof=1))
    if sd <= 0:
        return check("zero_kink", "statistics", "skip", "zero volatility: no distribution to inspect")
    w = 0.25 * sd
    below, above = int(np.sum((r >= -w) & (r < 0))), int(np.sum((r >= 0) & (r < w)))
    pb = _N.cdf((0 - mu) / sd) - _N.cdf((-w - mu) / sd)
    pa = _N.cdf((w - mu) / sd) - _N.cdf((0 - mu) / sd)
    total = below + above
    det = {"bin_width": w, "small_losses": below, "small_gains": above}
    if total < KINK_MIN_COUNT or pb + pa <= 0:
        return check("zero_kink", "statistics", "skip", f"only {total} returns near zero: too few for the test", det)
    p0 = pb / (pb + pa)
    z = (below - total * p0) / math.sqrt(total * p0 * (1 - p0))
    det.update(z=z, expected_small_losses=total * p0)
    if z <= KINK_Z:
        return check("zero_kink", "statistics", "warn",
                     f"small losses are missing: {below} small losses vs {above} small gains (expected about "
                     f"{total * p0:.1f} losses, z={z:.1f}); losses may be deferred or rounded up", det)
    return check("zero_kink", "statistics", "pass", f"no kink at zero ({below} small losses, {above} small gains, z={z:.1f})", det)


def implausible_consistency(r: np.ndarray, ppy: float) -> dict[str, Any]:
    """Share of positive periods against a normal with the same mean and std."""
    n = r.size
    mu, sd = float(r.mean()), float(np.std(r, ddof=1))
    if sd <= 0:
        return check("implausible_consistency", "statistics", "skip", "zero volatility")
    p = min(max(_N.cdf(mu / sd), 1e-6), 1 - 1e-6)
    obs = int(np.sum(r > 0))
    z = (obs - n * p) / math.sqrt(n * p * (1 - p))
    sharpe = mu / sd * math.sqrt(ppy)
    det = {"positive_share": obs / n, "expected_share": p, "z": z, "sharpe": sharpe}
    if z >= CONSISTENCY_Z:
        text = f"{obs / n:.0%} of periods are positive vs {p:.0%} expected for this mean and volatility (z={z:.1f})"
        if sharpe >= CONSISTENCY_SHARPE and ppy <= 13:
            return check("implausible_consistency", "statistics", "fail",
                         f"{text}, Sharpe {sharpe:.1f} on monthly data: Madoff-like smoothness", det)
        return check("implausible_consistency", "statistics", "warn", text, det)
    return check("implausible_consistency", "statistics", "pass",
                 f"{obs / n:.0%} positive periods vs {p:.0%} expected (z={z:.1f})", det)


def _decimals(r: np.ndarray, cap: int = 10) -> int:
    for d in range(cap + 1):
        if np.all(np.abs(np.round(r, d) - r) < 1e-12):
            return d
    return cap


def round_numbers(r: np.ndarray) -> dict[str, Any]:
    """Exact multiples of 5 bps (0.0005, which includes 0.001) against the share expected for the data's resolution."""
    d = _decimals(r)
    if d <= 4:
        return check("round_numbers", "integrity", "skip", f"data is rounded to {d} decimals", {"decimals": d})
    k = r / 0.0005
    share = float(np.mean(np.abs(k - np.round(k)) < 1e-9))
    expected = min(1.0, 10.0**-d / 0.0005)
    count = int(round(share * r.size))
    det = {"decimals": d, "round_share": share, "expected_share": expected}
    if count >= 4 and share > ROUND_FACTOR * expected:
        return check("round_numbers", "integrity", "warn",
                     f"{share:.0%} of returns are exact multiples of 5 bps vs {expected:.1%} expected: figures may be typed or rounded by hand", det)
    return check("round_numbers", "integrity", "pass", f"round-number share {share:.1%} (expected {expected:.1%})", det)


def track_record_significance(r: np.ndarray, ppy: float, n_strategies: int) -> tuple[dict[str, Any], dict[str, float]]:
    """PSR, DSR for ``n_strategies`` and the minimum track record length."""
    rep = deflated_sharpe(r, n_trials=n_strategies, periods_per_year=ppy)
    sr, skew, kurt = rep["sharpe_per_bar"], rep["skew"], rep["kurtosis"]
    if sr > 0:
        var = max(1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr, 1e-9)
        min_trl = 1.0 + var * (_N.inv_cdf(DSR_MIN) / sr) ** 2
        min_years = min_trl / ppy
    else:
        min_years = float("inf")
    det = {"psr": rep["psr"], "dsr": rep["deflated_sharpe"], "n_strategies": n_strategies,
           "min_track_record_years": min_years, "track_record_years": r.size / ppy}
    msg = (f"probabilistic Sharpe {rep['psr']:.2f}, deflated for {n_strategies} strategies {rep['deflated_sharpe']:.2f}; "
           f"track record {r.size / ppy:.1f} years, {min_years:.1f} needed")
    status = "pass" if rep["deflated_sharpe"] >= DSR_MIN else "fail"
    if status == "fail":
        msg = "track record is not significant: " + msg
    return check("track_record_significance", "statistics", status, msg, det), {"psr": rep["psr"], "dsr": rep["deflated_sharpe"]}


def max_drawdown(r: np.ndarray) -> float:
    """Largest peak-to-trough fall of compounded wealth, as a positive fraction."""
    wealth = np.concatenate([[1.0], np.cumprod(1.0 + r)])
    return float(np.max(1.0 - wealth / np.maximum.accumulate(wealth)))


def drawdown_consistency(r: np.ndarray, seed: int) -> dict[str, Any]:
    """Observed max drawdown against 500 iid-normal simulations with the same mean, std and length."""
    rng = np.random.default_rng(seed)
    sims = rng.normal(r.mean(), np.std(r, ddof=1), size=(DD_SIMS, r.size)).clip(-0.99, None)
    wealth = np.concatenate([np.ones((DD_SIMS, 1)), np.cumprod(1.0 + sims, axis=1)], axis=1)
    dd = np.max(1.0 - wealth / np.maximum.accumulate(wealth, axis=1), axis=1)
    p5, med = float(np.percentile(dd, DD_QUANTILE)), float(np.median(dd))
    obs = max_drawdown(r)
    det = {"observed": obs, "simulated_p5": p5, "simulated_median": med, "sims": DD_SIMS}
    if obs < p5:
        return check("drawdown_consistency", "statistics", "warn",
                     f"max drawdown {obs:.1%} is too shallow for this volatility (5th percentile of simulations {p5:.1%}, median {med:.1%})", det)
    return check("drawdown_consistency", "statistics", "pass", f"max drawdown {obs:.1%} within the simulated range (5th percentile {p5:.1%})", det)


__all__ = [
    "drawdown_consistency", "implausible_consistency", "max_drawdown", "return_smoothing", "round_numbers",
    "smoothing_weights", "track_record_significance", "zero_kink",
]
