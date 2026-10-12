"""Family A (signal power), part 1: IC, IC decay, quantile monotonicity."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.alpha._core import ic_series, newey_west_t, quantile_index, rank_rows
from monte_neo.alpha.panel import Panel
from monte_neo.alpha.signal_extra import (  # noqa: F401  (re-exported: family A lives in two modules)
    check_breadth_consistency,
    check_long_short_legs,
    check_selection_vs_timing,
    check_signal_placebo,
)
from monte_neo.verify.checks import check

T_THRESHOLD = 2.0
MIN_DATES = 20


def check_ic(panel: Panel, fwd: np.ndarray, horizon: int) -> dict[str, Any]:
    """A1: mean rank IC with a Newey-West t-stat (lag >= horizon-1, Bartlett kernel).

    Args:
        panel: Aligned scores and prices.
        fwd: Forward returns at ``horizon`` (targets only).
        horizon: Forward-return horizon in bars.

    Returns:
        A check row ``ic``: info if the mean IC is positive and |t| >= 2, otherwise warn.
    """
    ic = ic_series(panel.scores, fwd)
    n = int(np.isfinite(ic).sum())
    if n < MIN_DATES:
        return check("ic", "statistics", "skip", f"only {n} dates with an IC (need {MIN_DATES})", {"n_dates": n})
    lag = max(horizon - 1, int(np.floor(4 * (n / 100.0) ** (2 / 9))))
    mean, se, t = newey_west_t(ic, lag)
    sd = float(np.nanstd(ic, ddof=1))
    icir = mean / sd if sd > 0 else float("nan")
    details = {"mean_ic": mean, "std_ic": sd, "icir": icir, "t_stat": t, "se": se, "nw_lag": lag, "n_dates": n, "horizon": horizon,
               "hit_rate": float(np.mean(ic[np.isfinite(ic)] > 0))}
    if mean > 0 and abs(t) >= T_THRESHOLD:
        return check("ic", "statistics", "info", f"mean rank IC {mean:.4f} (t={t:.1f}, ICIR {icir:.2f}): the signal predicts returns", details)
    return check("ic", "statistics", "warn", f"mean rank IC {mean:.4f} (t={t:.1f}): no evidence the signal predicts returns", details)


def check_ic_decay(panel: Panel, horizon_max: int = 20) -> dict[str, Any]:
    """A2: IC at horizons 1..H, exponential half-life from a log-linear fit on positive values.

    Args:
        panel: Aligned scores and prices.
        horizon_max: Largest horizon (limited to a quarter of the history).

    Returns:
        A check row ``ic_decay`` (info, or skip when the history is too short).
    """
    big_h = min(horizon_max, len(panel.dates) // 4)
    if big_h < 2:
        return check("ic_decay", "statistics", "skip", "history too short for an IC decay curve")
    hs = np.arange(1, big_h + 1)
    ics = np.array([np.nanmean(ic_series(panel.scores, panel.forward_returns(int(h)))) for h in hs])
    best = int(hs[int(np.nanargmax(ics))])
    pos = np.isfinite(ics) & (ics > 0)
    half: float | None = None
    tau: float | None = None
    if pos.sum() >= 3:
        slope, _ = np.polyfit(hs[pos], np.log(ics[pos]), 1)
        if slope < 0:
            tau = float(-1.0 / slope)
            half = float(tau * np.log(2.0))
    details = {"horizons": hs.tolist(), "ic": ics.tolist(), "best_horizon": best, "tau": tau, "half_life": half}
    msg = f"best horizon {best}; " + (f"IC half-life {half:.1f} bars" if half is not None else "no exponential decay found (IC does not fall with horizon)")
    return check("ic_decay", "statistics", "info", msg, details)


def _bucket_means(panel: Panel, fwd: np.ndarray, q: int) -> tuple[np.ndarray, np.ndarray]:
    """(dates x q) mean forward return per quantile bucket and the dates that have a full set."""
    valid = np.isfinite(panel.scores) & np.isfinite(fwd)
    qi = quantile_index(panel.scores, valid, q)
    r0 = np.nan_to_num(fwd)
    out = np.full((len(fwd), q), np.nan)
    for k in range(q):
        m = qi == k
        cnt = m.sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[:, k] = np.where(cnt > 0, (r0 * m).sum(axis=1) / cnt, np.nan)
    return out, np.isfinite(out).all(axis=1)


def _spearman_vec(means: np.ndarray) -> np.ndarray:
    """Spearman between bucket index and each row of ``means`` (n_draws x q)."""
    q = means.shape[1]
    idx = np.arange(q, dtype=float) - (q - 1) / 2.0
    r = rank_rows(means)
    r = r - r.mean(axis=1, keepdims=True)
    den = np.sqrt((r * r).sum(axis=1) * (idx * idx).sum())
    with np.errstate(divide="ignore", invalid="ignore"):
        return (r * idx).sum(axis=1) / den


def check_quantile_monotonicity(panel: Panel, fwd: np.ndarray, quantiles: int = 5, seed: int = 0, n_boot: int = 500, block: int = 10) -> dict[str, Any]:
    """A3: equal-weight quantile portfolios, spread, adjacent increases and a block bootstrap.

    Args:
        panel: Aligned scores and prices.
        fwd: Forward returns (targets only).
        quantiles: Number of buckets (default 5).
        seed: Seed for the date-block bootstrap.
        n_boot: Bootstrap draws.
        block: Block length in dates.

    Returns:
        A check row ``quantile_monotonicity``: pass if returns rise across buckets, warn if
        they are not monotone (e.g. all profit sits in one extreme bucket).
    """
    means, full = _bucket_means(panel, fwd, quantiles)
    m = means[full]
    if len(m) < MIN_DATES:
        return check("quantile_monotonicity", "statistics", "skip", f"only {len(m)} dates with all {quantiles} buckets")
    avg = m.mean(axis=0)
    inc = float(np.mean(np.diff(avg) > 0))
    spread = float(avg[-1] - avg[0])
    rng = np.random.default_rng(seed)
    n = len(m)
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, max(n - block, 1), size=(n_boot, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_boot, -1)[:, :n]
    rho = _spearman_vec(m[idx].mean(axis=1))
    rho_real = float(_spearman_vec(avg[None, :])[0])
    p_pos = float(np.mean(rho > 0))
    lo = float(np.nanpercentile(rho, 5))
    details = {"quantile_mean_return": avg.tolist(), "spread": spread, "adjacent_increase_share": inc, "spearman": rho_real,
               "bootstrap_spearman_p5": lo, "bootstrap_share_positive": p_pos, "n_dates": n, "quantiles": quantiles}
    if inc >= 0.75 and spread > 0 and lo > 0:
        return check("quantile_monotonicity", "statistics", "pass", f"returns rise across {quantiles} buckets (rank corr {rho_real:.2f}, spread {spread:.4%} per period)", details)
    return check("quantile_monotonicity", "statistics", "warn", f"bucket returns are not monotone ({inc:.0%} adjacent increases, rank corr {rho_real:.2f}): profit may sit in one extreme", details)
