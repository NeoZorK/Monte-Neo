"""Family E, null and perturbation checks: synthetic markets, score noise, second vendor, bar grid."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.alpha.panel import Panel
from monte_neo.alpha.robustness_common import ann_sharpe, periods_per_year, rnd, spread, spread_parts, step_seconds
from monte_neo.verify.checks import check

N_SYNTH = 100
BLOCK = 20
NOISE_LEVELS = (0.1, 0.25, 0.5)
NOISE_REPEATS = 20


def block_indices(n_bars: int, n_paths: int, rng: np.random.Generator, mean_block: int = BLOCK) -> np.ndarray:
    """Stationary-bootstrap row indices, shape (n_paths, n_bars): geometric blocks, wrapping around."""
    t = np.arange(n_bars)
    new = rng.random((n_paths, n_bars)) < 1.0 / mean_block
    new[:, 0] = True
    start = rng.integers(0, n_bars, size=(n_paths, n_bars))
    last = np.maximum.accumulate(np.where(new, t, 0), axis=1)
    return (np.take_along_axis(start, last, axis=1) + (t - last)) % n_bars


def synthetic_market_null(panel: Panel, quantiles: int, seed: int, cost_bps: float) -> dict[str, Any]:
    """E5: share of block-bootstrapped markets where the same scores earn at least the real net Sharpe.

    Whole dates are resampled in blocks (mean length 20), so the cross-section and its correlation
    stay intact, while the scores stay on the original date index: the score/return link breaks,
    market statistics do not. The synthetic close is the cumulative product of the resampled
    returns; only returns enter the portfolio, so the weights (a function of the scores) are fixed.
    """
    net, w, ret, cost = spread_parts(panel.close, panel.scores, quantiles, cost_bps)
    ppy = periods_per_year(panel)
    if len(net) < 60:
        return check("synthetic_market_null", "statistics", "skip", "history too short for a block bootstrap", {})
    real = ann_sharpe(net, ppy)
    held = np.vstack([np.zeros((1, w.shape[1])), w[:-1]])
    idx = block_indices(len(net), N_SYNTH, np.random.default_rng(seed))
    sims = np.empty(N_SYNTH)
    for i in range(N_SYNTH):
        sims[i] = ann_sharpe((held * ret[idx[i]]).sum(axis=1) - cost, ppy)
    p = float((np.sum(sims >= real) + 1) / (N_SYNTH + 1))
    details = {
        "real_net_sharpe": rnd(real), "null_median_sharpe": rnd(np.median(sims)),
        "null_p95_sharpe": rnd(np.quantile(sims, 0.95)), "p_value": rnd(p), "n_synthetic": N_SYNTH, "block": BLOCK,
    }
    summary = f"net Sharpe {real:.2f} vs {np.median(sims):.2f} median on {N_SYNTH} synthetic markets (p = {p:.3f})"
    if real <= 0 or p > 0.10:
        return check("synthetic_market_null", "statistics", "fail", summary + ": not distinguishable from the market-only null", details)
    return check("synthetic_market_null", "statistics", "pass", summary, details)


def noise_injection(panel: Panel, quantiles: int, seed: int, cost_bps: float) -> dict[str, Any]:
    """E6: Gaussian noise (0.1, 0.25, 0.5 x the cross-sectional score std) added to the scores."""
    ppy = periods_per_year(panel)
    base = ann_sharpe(spread(panel.close, panel.scores, quantiles, cost_bps), ppy)
    if base <= 0:
        return check("noise_injection", "statistics", "skip", f"net Sharpe {base:.2f} is not positive: nothing to degrade", {})
    rng = np.random.default_rng(seed)
    with np.errstate(invalid="ignore"):
        sd = np.nanstd(panel.scores, axis=1, keepdims=True)
    sd = np.where(np.isfinite(sd) & (sd > 0), sd, 1.0)
    means: dict[str, float | None] = {}
    for lvl in NOISE_LEVELS:
        vals = [
            ann_sharpe(spread(panel.close, panel.scores + lvl * sd * rng.standard_normal(panel.scores.shape), quantiles, cost_bps), ppy)
            for _ in range(NOISE_REPEATS)
        ]
        means[str(lvl)] = rnd(np.mean(vals))
    first = float(means[str(NOISE_LEVELS[0])] or 0.0)
    details = {"original_net_sharpe": rnd(base), "mean_net_sharpe_by_noise": means, "repeats": NOISE_REPEATS}
    summary = "net Sharpe " + f"{base:.2f} -> " + ", ".join(f"{means[str(v)]} at {v}x" for v in NOISE_LEVELS)
    if first < 0.5 * base:
        return check("noise_injection", "statistics", "warn", summary + ": the edge depends on exact score values", details)
    return check("noise_injection", "statistics", "pass", summary, details)


def data_source_replication(panel: Panel, quantiles: int, alt_close: Any, cost_bps: float) -> dict[str, Any]:
    """E7: same scores on a second vendor's prices (array or DataFrame of dates x symbols)."""
    if alt_close is None:
        return check("data_source_replication", "statistics", "skip", "no second price source given", {})
    if isinstance(alt_close, pd.DataFrame):
        alt = alt_close.reindex(index=panel.dates, columns=panel.symbols).to_numpy(dtype=np.float64)
    else:
        alt = np.asarray(alt_close, dtype=np.float64)
    if alt.shape != panel.close.shape:
        return check("data_source_replication", "statistics", "skip", f"second source has shape {alt.shape}, expected {panel.close.shape}", {})
    ppy = periods_per_year(panel)
    net1 = spread(panel.close, panel.scores, quantiles, cost_bps)
    net2 = spread(alt, panel.scores, quantiles, cost_bps)
    s1, s2 = ann_sharpe(net1, ppy), ann_sharpe(net2, ppy)
    with np.errstate(divide="ignore", invalid="ignore"):
        r1, r2 = panel.close[1:] / panel.close[:-1] - 1.0, alt[1:] / alt[:-1] - 1.0
    ok = np.isfinite(r1) & np.isfinite(r2)
    corr = float(np.corrcoef(r1[ok], r2[ok])[0, 1]) if ok.sum() > 2 else float("nan")
    diff = abs(s2 - s1) / abs(s1) if s1 != 0 else float("inf") if s2 != 0 else 0.0
    flip = bool(s1 * s2 < 0)
    details = {"return_correlation": rnd(corr), "net_sharpe_primary": rnd(s1), "net_sharpe_second": rnd(s2), "relative_difference": rnd(diff), "sign_flip": flip}
    summary = f"per-bar return correlation {corr:.3f}; net Sharpe {s1:.2f} vs {s2:.2f} on the second source"
    if flip or diff > 0.5:
        return check("data_source_replication", "statistics", "warn", summary + (": sign flips" if flip else ": Sharpe differs by more than 50%"), details)
    return check("data_source_replication", "statistics", "pass", summary, details)


def bar_construction(panel: Panel, quantiles: int, cost_bps: float) -> dict[str, Any]:
    """E8: intraday only. Compares net returns on even and odd bars; a half-bar shift is not possible on bars.

    If the profit lives on one half of the bar grid (and the other half has the opposite sign), the
    result depends on how the bars are cut. Daily data is skipped.
    """
    if len(panel.dates) < 2 or step_seconds(panel) >= 20 * 3600:
        return check("bar_construction", "statistics", "skip", "daily or slower bars: the bar grid is the calendar day", {})
    net = spread(panel.close, panel.scores, quantiles, cost_bps)
    ppy = periods_per_year(panel) / 2.0
    even, odd = net[0::2], net[1::2]
    se, so = ann_sharpe(even, ppy), ann_sharpe(odd, ppy)
    details = {"mean_even": rnd(even.mean(), 8), "mean_odd": rnd(odd.mean(), 8), "sharpe_even": rnd(se), "sharpe_odd": rnd(so)}
    summary = f"net Sharpe on even bars {se:.2f}, on odd bars {so:.2f}"
    if even.mean() * odd.mean() < 0:
        return check("bar_construction", "statistics", "warn", summary + ": the halves have opposite signs", details)
    return check("bar_construction", "statistics", "pass", summary, details)
