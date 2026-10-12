"""Family F: statistics across all attempts (multiple testing, selection bias, plausibility of the drawdown).

A single backtest is judged against what the whole search could produce by luck: the Harvey-Liu-Zhu hurdle, false
discovery rates over the ledger of variants, a stepdown across variants, the minimum backtest length, and a haircut on
the Sharpe ratio. Only numpy, pandas and the standard library are used.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.alpha._core import newey_west_t
from monte_neo.verify.checks import check

HLZ_HURDLE = 3.0
FDR_LEVEL = 0.10
_N = NormalDist()

NEXT_ACTIONS: dict[str, str] = {
    "hlz_hurdle": "A t-stat below 3 is within what a large search finds by luck: collect more history or test out-of-sample before trusting it.",
    "fdr_across_ledger": "After correcting for every variant you tried, this one is not clearly real: report all variants tried and test the best one on new data.",
    "romano_wolf": "Only the variants listed survive the family-wise test across all of them: drop or re-test the rest.",
    "min_backtest_length": "The history is shorter than the search needs: extend the sample or cut the number of variants tried.",
    "drawdown_plausibility": "The drawdown does not match the volatility: too small points to smoothing, stale prices or overfitting; too large points to fat tails or regime risk. Inspect the worst and quietest periods.",
    "haircut_sharpe": "Plan with the haircut Sharpe, not the raw one: it prices the number of variants tried.",
}


def _p_two_sided(t: np.ndarray | float) -> np.ndarray:
    return np.vectorize(lambda v: math.erfc(abs(v) / math.sqrt(2.0)))(np.asarray(t, dtype=float))


def _nw_lag(n: int) -> int:
    return int(4 * (n / 100.0) ** (2 / 9))


def _sharpe_ann(r: np.ndarray, ppy: float) -> float:
    sd = float(np.std(r, ddof=1))
    return float(np.mean(r) / sd * math.sqrt(ppy)) if sd > 0 else 0.0


def hlz_hurdle(r: np.ndarray) -> dict[str, Any]:
    """F1: Newey-West t-stat of the mean return against the Harvey-Liu-Zhu hurdle of 3.0 (pass >= 3, warn 2..3, info below 2)."""
    _, _, t = newey_west_t(np.asarray(r, float), _nw_lag(len(r)))
    details = {"t_stat": t, "hurdle": HLZ_HURDLE}
    if not math.isfinite(t) or t < 2.0:
        return check("hlz_hurdle", "statistics", "info", f"t = {t:.2f}, below 2 (the no-edge check owns this case)", details)
    if t < HLZ_HURDLE:
        return check("hlz_hurdle", "statistics", "warn", f"t = {t:.2f} is above 2 but below the Harvey-Liu-Zhu hurdle of 3.0", details)
    return check("hlz_hurdle", "statistics", "pass", f"t = {t:.2f} clears the Harvey-Liu-Zhu hurdle of 3.0", details)


def bhy_qvalues(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg-Yekutieli adjusted p-values (q-values), valid under any dependence."""
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p)
    c = float(np.sum(1.0 / np.arange(1, m + 1)))
    q = p[order] * m * c / np.arange(1, m + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(q, 1.0)
    return out


def fdr_across_ledger(t_stats: list[float], current_index: int = -1) -> dict[str, Any]:
    """F2: BHY q-values over all variants' t-stats; warn if the current variant's q exceeds 0.10."""
    t = np.asarray(t_stats, float)
    q = bhy_qvalues(_p_two_sided(t))
    qc = float(q[current_index])
    details = {"n_variants": len(t), "q_current": qc, "t_current": float(t[current_index]), "n_significant": int((q <= FDR_LEVEL).sum())}
    s = f"q-value {qc:.3f} among {len(t)} variants (BHY)"
    if qc > FDR_LEVEL:
        return check("fdr_across_ledger", "statistics", "warn", s + ": above 0.10", details)
    return check("fdr_across_ledger", "statistics", "pass", s, details)


def t_stats_from_ledger(entries: list[dict[str, Any]], data_id: str, n_bars: int, ppy: float = 252.0) -> list[float]:
    """Convert ledger entries on one dataset to t-stats, t = SR_per_bar * sqrt(n_bars).

    Assumes the ledger ``sharpe`` is annualised with ``ppy`` periods per year and that every variant was run on the same
    ``n_bars``; the last entry per variant wins.

    Args:
        entries: Ledger entries (dicts with ``data``, ``variant``, ``sharpe``).
        data_id: Keep only entries on this data.
        n_bars: Number of bars of the backtests.
        ppy: Periods per year used to annualise the ledger Sharpe.
    """
    latest: dict[Any, float] = {}
    for i, e in enumerate(entries):
        if e.get("data") == data_id and e.get("sharpe") is not None:
            latest[e.get("variant", f"#{i}")] = float(e["sharpe"])
    return [sr / math.sqrt(ppy) * math.sqrt(n_bars) for sr in latest.values()]


def romano_wolf(returns_matrix: np.ndarray, alpha: float = 0.05, draws: int = 500, seed: int = 0) -> dict[str, Any]:
    """F3: Romano-Wolf stepdown over M variants with a circular block bootstrap of studentised means.

    Args:
        returns_matrix: T x M returns, one column per variant.
        alpha: Family-wise error rate.
        draws: Bootstrap draws.
        seed: RNG seed.
    """
    x = np.asarray(returns_matrix, float)
    n, m = x.shape
    mean, sd = x.mean(0), x.std(0, ddof=1)
    se = np.where(sd > 0, sd / math.sqrt(n), np.inf)
    t = mean / se
    block = max(1, round(n ** (1 / 3)))
    nb = -(-n // block)
    csum = np.vstack([np.zeros(m), np.cumsum(np.vstack([x, x]), axis=0)])
    starts = np.random.default_rng(seed).integers(0, n, size=(draws, nb))
    sums = csum[starts + block] - csum[starts]
    boot_t = (sums.sum(1) / (nb * block) - mean) / se
    order = np.argsort(-np.abs(t))
    rejected = np.zeros(m, bool)
    for k in range(m):
        rest = order[k:]
        crit = np.quantile(np.abs(boot_t[:, rest]).max(1), 1 - alpha)
        if abs(t[order[k]]) <= crit:
            break
        rejected[order[k]] = True
    sig = [int(i) for i in np.flatnonzero(rejected)]
    s = f"{len(sig)} of {m} variants significant at family-wise {alpha:.0%}"
    return check("romano_wolf", "statistics", "info", s, {"significant": sig, "t_stats": [float(v) for v in t], "alpha": alpha})


def min_backtest_length(sharpe_annual: float, n_trials: int, years: float) -> dict[str, Any]:
    """F4: Minimum Backtest Length (Bailey and Lopez de Prado, "The Probability of Backtest Overfitting").

    Approximation: years needed ~ 2 ln(N) / SR_annual^2, the history after which the best of N luck-only strategies
    stops reaching this Sharpe. Warn if the history is shorter; fail if shorter than half and N >= 10.
    """
    n = max(1, int(n_trials))
    needed = 2.0 * math.log(n) / (sharpe_annual**2) if sharpe_annual != 0 else float("inf")
    details = {"years_needed": needed, "years_available": years, "n_trials": n, "sharpe_annual": sharpe_annual}
    if sharpe_annual <= 0:
        s = f"{years:.1f} years of history; Sharpe {sharpe_annual:.2f} is not positive, so no length of history separates it from luck"
    else:
        need_txt = "less than a month" if needed < 1 / 12 else f"about {needed:.1f} years"
        s = f"{years:.1f} years of history; {need_txt} needed to separate Sharpe {sharpe_annual:.2f} from the best of {n} luck-only variants"
    if years >= needed:
        return check("min_backtest_length", "statistics", "pass", s, details)
    status = "fail" if (years < needed / 2 and n >= 10) else "warn"
    return check("min_backtest_length", "statistics", status, s, details)


def _max_drawdown(r: np.ndarray) -> np.ndarray:
    eq = np.cumprod(1.0 + np.atleast_2d(r), axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.ones((eq.shape[0], 1)), eq], axis=1), axis=1)[:, 1:]
    return (1.0 - eq / peak).max(axis=1)


def drawdown_plausibility(r: np.ndarray, ppy: float, seed: int = 0, sims: int = 500) -> dict[str, Any]:
    """F5: observed max drawdown against iid normal returns with the same mean, std and length (5th..99th percentile)."""
    r = np.asarray(r, float)
    sim = np.random.default_rng(seed).normal(r.mean(), r.std(ddof=1), size=(sims, len(r)))
    lo, hi = (float(v) for v in np.percentile(_max_drawdown(sim), [5, 99]))
    dd = float(_max_drawdown(r)[0])
    details = {"observed_max_dd": dd, "sim_p5": lo, "sim_p99": hi, "sims": sims}
    s = f"max drawdown {dd:.1%} vs {lo:.1%}..{hi:.1%} for iid returns with the same mean and volatility"
    if dd < lo:
        return check("drawdown_plausibility", "statistics", "warn", s + ": too smooth for its volatility (smoothing, stale prices or overfitting)", details)
    if dd > hi:
        return check("drawdown_plausibility", "statistics", "warn", s + ": deeper than iid returns produce (fat tails or regime risk)", details)
    return check("drawdown_plausibility", "statistics", "pass", s, details)


def haircut_sharpe(sharpe_annual: float, n_obs: int, n_trials: int, ppy: float) -> dict[str, Any]:
    """F6: Harvey-Liu Sharpe haircut with Bonferroni and Holm-Sidak adjusted p-values for the best of N trials."""
    n = max(1, int(n_trials))
    t = sharpe_annual * math.sqrt(n_obs / ppy)
    p = max(math.erfc(abs(t) / math.sqrt(2.0)), 1e-300)
    adj = {"bonferroni": min(1.0, p * n), "holm_sidak": 1.0 - (1.0 - p) ** n if p > 1e-12 else min(1.0, p * n)}
    out: dict[str, Any] = {"t_stat": t, "p_raw": p, "n_trials": n}
    for name, pa in adj.items():
        t_adj = -_N.inv_cdf(max(pa, 1e-300) / 2.0) if pa < 1.0 else 0.0
        sr_h = math.copysign(t_adj, sharpe_annual) * math.sqrt(ppy / n_obs)
        out[name] = {"p_adj": pa, "sharpe_haircut": sr_h, "haircut_pct": (1.0 - sr_h / sharpe_annual) * 100.0 if sharpe_annual else 0.0}
    b = out["bonferroni"]
    noun = "trial" if n == 1 else "trials"
    s = f"Sharpe {sharpe_annual:.2f} becomes {b['sharpe_haircut']:.2f} after Bonferroni for {n} {noun} (haircut {b['haircut_pct']:.0f}%)"
    return check("haircut_sharpe", "statistics", "info", s, out)


def run_multiple_testing(
    r: np.ndarray, ppy: float, n_trials: int, t_stats: list[float] | None = None,
    timestamps: pd.DatetimeIndex | None = None, seed: int = 0,
) -> list[dict[str, Any]]:
    """Run F1, F4, F5, F6 (and F2 when ``t_stats`` is given; the current variant is the last entry).

    Args:
        r: Strategy returns per bar.
        ppy: Periods per year.
        n_trials: Variants tried.
        t_stats: Optional t-stats of every variant in the ledger, current last.
        timestamps: Bar dates; years come from the span, else from ``len(r) / ppy``.
        seed: Simulation seed.
    """
    r = np.asarray(r, float)
    years = len(r) / ppy
    if timestamps is not None and len(timestamps) > 1:
        years = (pd.Timestamp(timestamps[-1]) - pd.Timestamp(timestamps[0])).days / 365.25
    sr = _sharpe_ann(r, ppy)
    rows = [hlz_hurdle(r), min_backtest_length(sr, n_trials, years), drawdown_plausibility(r, ppy, seed), haircut_sharpe(sr, len(r), n_trials, ppy)]
    if t_stats is not None and len(t_stats) >= 2:
        rows.insert(1, fdr_across_ledger(list(t_stats), -1))
    return rows


__all__ = [
    "NEXT_ACTIONS", "bhy_qvalues", "drawdown_plausibility", "fdr_across_ledger", "haircut_sharpe", "hlz_hurdle",
    "min_backtest_length", "romano_wolf", "run_multiple_testing", "t_stats_from_ledger",
]
