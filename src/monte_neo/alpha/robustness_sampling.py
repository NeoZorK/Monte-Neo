"""Family E, sampling checks: universe subsets, groups, start dates, disjoint-period paths."""

from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np

from monte_neo.alpha.panel import Panel
from monte_neo.alpha.robustness_common import (
    MIN_BARS,
    ann_return,
    ann_sharpe,
    periods_per_year,
    rnd,
    spread,
    spread_parts,
)
from monte_neo.verify.checks import check

SUBSET_SHARE = 0.7
N_SUBSETS = 100
TOP_N = 5


# Symbol-level noise alone gives the top 5 of 40 symbols about half the profit of an honest edge (zoo A15).
TOP_SHARE_WARN = 0.7


def universe_subsampling(panel: Panel, quantiles: int, seed: int, cost_bps: float) -> dict[str, Any]:
    """E1: does the edge survive random 70 % subsets of the symbols, and is it spread over many names?"""
    n = len(panel.symbols)
    k = int(round(SUBSET_SHARE * n))
    if n < 6 or k < 4:
        return check("universe_subsampling", "statistics", "skip", f"only {n} symbols: too few to subsample", {})
    rng = np.random.default_rng(seed)
    ppy = periods_per_year(panel)
    rets, sharpes = [], []
    for _ in range(N_SUBSETS):
        cols = np.sort(rng.choice(n, size=k, replace=False))
        net = spread(panel.close[:, cols], panel.scores[:, cols], quantiles, cost_bps)
        rets.append(ann_return(net, ppy))
        sharpes.append(ann_sharpe(net, ppy))
    pos = float(np.mean(np.array(rets) > 0.0))
    net, w, ret, _ = spread_parts(panel.close, panel.scores, quantiles, cost_bps)
    held = np.vstack([np.zeros((1, w.shape[1])), w[:-1]])
    contrib = (held * ret).sum(axis=0)
    total = float(contrib.sum())
    top = float(np.sort(contrib)[::-1][:TOP_N].sum() / total) if total > 0 else float("nan")
    med = float(np.median(sharpes))
    details = {
        "n_subsets": N_SUBSETS, "subset_symbols": k, "share_positive": rnd(pos), "median_sharpe": rnd(med),
        "top5_profit_share": rnd(top), "top_symbols": [panel.symbols[i] for i in np.argsort(-contrib)[:TOP_N]],
    }
    top_txt = "no share of the profit (there is no gross profit)" if not np.isfinite(top) else f"{top:.0%} of the profit"
    summary = f"{pos:.0%} of {N_SUBSETS} random {SUBSET_SHARE:.0%} subsets earn a positive net return (median Sharpe {med:.2f}); top-5 symbols give {top_txt}"
    if pos < 0.5:
        return check("universe_subsampling", "statistics", "fail", summary + ": the result does not hold on most subsets", details)
    if pos < 0.8 or (np.isfinite(top) and top > TOP_SHARE_WARN):
        return check("universe_subsampling", "statistics", "warn", summary + ": the edge leans on a few names", details)
    return check("universe_subsampling", "statistics", "pass", summary, details)


def group_split(
    panel: Panel, quantiles: int, groups: dict[str, str] | None, cost_bps: float
) -> dict[str, Any]:
    """E2: is the profit earned in one sector/country only? Each group is ranked within itself."""
    if not groups:
        return check("group_split", "statistics", "skip", "no groups given (sector/country per symbol)", {})
    ppy = periods_per_year(panel)
    min_size = max(4, quantiles)
    out: dict[str, dict[str, float | None]] = {}
    profits: dict[str, float] = {}
    for g in sorted({groups[s] for s in panel.symbols if s in groups}, key=str):
        cols = [i for i, s in enumerate(panel.symbols) if groups.get(s) == g]
        if len(cols) < min_size:
            continue
        net = spread(panel.close[:, cols], panel.scores[:, cols], quantiles, cost_bps)
        profits[str(g)] = ann_return(net, ppy)
        out[str(g)] = {"symbols": len(cols), "ann_return": rnd(profits[str(g)]), "sharpe": rnd(ann_sharpe(net, ppy))}
    if len(profits) < 2:
        return check("group_split", "statistics", "skip", f"fewer than 2 groups with at least {min_size} symbols", {"groups": out})
    pos = {g: p for g, p in profits.items() if p > 0}
    best = max(profits, key=lambda g: profits[g])
    share = profits[best] / sum(pos.values()) if pos else float("nan")
    details = {"groups": out, "best_group": best, "best_group_profit_share": rnd(share)}
    if not pos:
        return check("group_split", "statistics", "warn", "no group earns a positive net return", details)
    summary = f"{len(profits)} groups; '{best}' gives {share:.0%} of the positive group profit"
    if share > 0.7:
        return check("group_split", "statistics", "warn", summary + ": the profit comes from one group", details)
    return check("group_split", "statistics", "pass", summary, details)


def start_date_sensitivity(panel: Panel, quantiles: int, cost_bps: float) -> dict[str, Any]:
    """E3: annual return when the backtest starts 0..12 steps (T/40 bars each) later."""
    net = spread(panel.close, panel.scores, quantiles, cost_bps)
    step = max(1, len(net) // 40)
    ppy = periods_per_year(panel)
    starts = [i * step for i in range(13) if len(net) - i * step >= MIN_BARS]
    if len(starts) < 2:
        return check("start_date_sensitivity", "statistics", "skip", "history too short to move the start date", {})
    vals = np.array([ann_return(net[s:], ppy) for s in starts])
    spr, med_abs = float(vals.max() - vals.min()), float(np.median(np.abs(vals)))
    loses = bool(vals[0] > 0 and np.any(vals < 0))
    details = {
        "step_bars": step, "ann_returns": [rnd(v) for v in vals], "spread": rnd(spr),
        "median_abs": rnd(med_abs), "some_start_loses_while_full_wins": loses,
    }
    summary = f"annual return over {len(starts)} start dates ranges {vals.min():.2%} to {vals.max():.2%}"
    if spr > med_abs or loses:
        why = "a later start loses while the full sample wins" if loses else "the range exceeds the median absolute return"
        return check("start_date_sensitivity", "statistics", "warn", f"{summary}: {why}", details)
    return check("start_date_sensitivity", "statistics", "pass", summary, details)


def cpcv_paths(panel: Panel, quantiles: int, horizon: int, cost_bps: float, n_groups: int = 6, k_test: int = 2) -> dict[str, Any]:
    """E4: combinatorial purged cross-validation over disjoint periods.

    Dates are cut into ``n_groups`` blocks; every choice of ``k_test`` blocks (15 for 6 choose 2)
    is one test set, with ``horizon`` bars purged at both ends of each test block. The score here
    is a fixed signal, so nothing is refitted and CPCV measures stability of the net Sharpe across
    disjoint periods; with a fit/predict model the training blocks would be refitted per
    combination (out of scope).
    """
    net = spread(panel.close, panel.scores, quantiles, cost_bps)
    if len(net) < n_groups * MIN_BARS:
        return check("cpcv_paths", "statistics", "skip", "history too short for 6 blocks of at least 30 bars", {})
    blocks = np.array_split(np.arange(len(net)), n_groups)
    h = max(0, horizon)
    ppy = periods_per_year(panel)
    sharpes = []
    for combo in combinations(range(n_groups), k_test):
        idx = np.concatenate([blocks[g][h : len(blocks[g]) - h] for g in combo])
        sharpes.append(ann_sharpe(net[idx], ppy))
    arr = np.array(sharpes)
    share = float(np.mean(arr > 0))
    details = {
        "blocks": n_groups, "test_blocks": k_test, "combinations": len(arr), "backtest_paths": len(arr) * k_test // n_groups,
        "min_sharpe": rnd(arr.min()), "median_sharpe": rnd(np.median(arr)), "share_positive": rnd(share), "purge_bars": h,
    }
    summary = f"net Sharpe over {len(arr)} test combinations: min {arr.min():.2f}, median {np.median(arr):.2f}, {share:.0%} positive"
    return check("cpcv_paths", "statistics", "warn" if share < 0.6 else "info", summary, details)
