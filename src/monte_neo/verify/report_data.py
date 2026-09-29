"""Data behind the report's charts: compact, derived from the run, not part of the certificate id.

Every block is small (the whole ``charts`` section stays around 10 KB) so a certificate
remains a document that is easy to store and to send.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

import numpy as np

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.breakdown import _parse_times
from monte_neo.verify.engine import total_return as _total_return
from monte_neo.verify.stats import bar_returns

HIST_BINS = 30
ROLLING_POINTS = 100
COST_LEVELS_BPS = (0.0, 2.5, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0)
MAX_TRADES_FOR_STATS = 20_000
MIN_MONTHLY_SPAN_DAYS = 60


def monthly_returns(equity: np.ndarray, timestamps: Any, start: int) -> list[list[float]]:
    """``[[year, month, return], ...]`` for every calendar month from the end of warm-up.

    A month's return runs from the previous month's last bar to its own last bar. Empty
    without timestamps or for a span under two months.
    """
    n = equity.size
    times = _parse_times(timestamps, n)
    if times is None or n - start < 2 or (times[n - 1] - times[start]).days < MIN_MONTHLY_SPAN_DAYS:
        return []
    codes = np.asarray(times.year) * 100 + np.asarray(times.month)
    firsts = np.concatenate([[start], np.flatnonzero(np.diff(codes[start:]) != 0) + start + 1])
    lasts = np.concatenate([firsts[1:] - 1, [n - 1]])
    out = []
    for a, b in zip(firsts, lasts, strict=True):
        base = max(start, int(a) - 1)
        ret = float(equity[b] / equity[base] - 1.0) if equity[base] > 0 else 0.0
        out.append([int(codes[a] // 100), int(codes[a] % 100), round(ret, 5)])
    return out


def returns_histogram(rets: np.ndarray, bins: int = HIST_BINS) -> dict[str, Any]:
    """Counts of non-zero per-bar returns in equal bins between the 0.5th and 99.5th percentiles (tails fold into the ends)."""
    r = np.asarray(rets, dtype=np.float64)
    r = r[np.isfinite(r) & (r != 0.0)]  # bars without a position or price change carry no information
    if r.size < 20 or float(np.ptp(r)) == 0.0:
        return {}
    lo, hi = np.percentile(r, [0.5, 99.5])
    if hi <= lo:
        return {}
    counts, edges = np.histogram(np.clip(r, lo, hi), bins=bins, range=(lo, hi))
    return {
        "edges": [round(float(e), 6) for e in edges],
        "counts": [int(c) for c in counts],
        "mean": round(float(r.mean()), 6),
        "std": round(float(r.std(ddof=1)), 6),
        "n": int(r.size),
    }


def rolling_sharpe(rets: np.ndarray, periods_per_year: float, points: int = ROLLING_POINTS) -> dict[str, Any]:
    """Annualized Sharpe over a trailing window (a tenth of the sample, at least 30 bars), sampled evenly."""
    r = np.asarray(rets, dtype=np.float64)
    window = max(30, r.size // 10)
    if r.size < window + 5:
        return {}
    c1 = np.concatenate([[0.0], np.cumsum(r)])
    c2 = np.concatenate([[0.0], np.cumsum(r * r)])
    ends = np.arange(window, r.size + 1)
    mean = (c1[ends] - c1[ends - window]) / window
    var = np.maximum((c2[ends] - c2[ends - window]) / window - mean * mean, 0.0) * window / (window - 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        values = np.where(var > 1e-30, mean / np.sqrt(var), 0.0) * math.sqrt(max(periods_per_year, 1.0))
    pick = np.unique(np.linspace(0, values.size - 1, num=min(points, values.size)).astype(int))
    return {"window": int(window), "values": [round(float(values[i]), 3) for i in pick]}


def cost_curve(
    ohlc: dict[str, np.ndarray], positions: np.ndarray, model: ExecutionModel, levels: tuple[float, ...] = COST_LEVELS_BPS
) -> dict[str, Any]:
    """Net return when the per-side cost (commission, no slippage) is 0 ... 50 bps, and the modeled cost."""
    points = [
        {"bps": lvl, "return": round(float(_total_return(ohlc, positions, replace(model, commission_bps=lvl, slippage_bps=0.0, impact_bps=0.0))), 5)}
        for lvl in levels
    ]
    return {"modeled_bps": round(float(model.commission_bps + model.effective_slip_bps), 3), "points": points}


def _streak(flags: np.ndarray) -> int:
    best = run = 0
    for f in flags:
        run = run + 1 if f else 0
        best = max(best, run)
    return best


def trade_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Win rate, profit factor, average win / loss, holding time, extremes and streaks of closed trades."""
    if not trades:
        return {}
    pnl = np.array([t["pnl"] for t in trades], dtype=np.float64)
    cost = np.array([abs(t["qty"]) * t["entry_px"] for t in trades], dtype=np.float64)
    ret = np.divide(pnl, cost, out=np.zeros_like(pnl), where=cost > 0)
    hold = np.array([t["exit_idx"] - t["entry_idx"] for t in trades], dtype=np.float64)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    return {
        "n": len(trades),
        "win_rate": round(float(np.mean(pnl > 0)), 4),
        "profit_factor": round(float(wins.sum() / -losses.sum()), 3) if losses.size and wins.size else None,
        "avg_win": round(float(ret[pnl > 0].mean()), 5) if wins.size else None,
        "avg_loss": round(float(ret[pnl < 0].mean()), 5) if losses.size else None,
        "best": round(float(ret.max()), 5),
        "worst": round(float(ret.min()), 5),
        "avg_hold_bars": round(float(hold.mean()), 2),
        "max_consecutive_wins": _streak(pnl > 0),
        "max_consecutive_losses": _streak(pnl < 0),
    }


def build_charts(
    *,
    run: dict[str, Any],
    ohlc: dict[str, np.ndarray],
    positions: np.ndarray,
    model: ExecutionModel,
    timestamps: Any,
    periods_per_year: float,
    timing: dict[str, Any] | None,
    trades: list[dict[str, Any]] | None,
    spread: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The ``charts`` section of a certificate."""
    rets = bar_returns(run["equity"], start=model.warmup_bars)
    out: dict[str, Any] = {
        "monthly": monthly_returns(run["equity"], timestamps, model.warmup_bars),
        "returns_hist": returns_histogram(rets),
        "rolling_sharpe": rolling_sharpe(rets, periods_per_year),
        "cost_curve": cost_curve(ohlc, positions, model),
    }
    if spread and "cost_curve" in out:
        out["cost_curve"]["estimated_half_spread_bps"] = spread["half_spread_bps"]
    if timing and timing.get("shifted_returns"):
        out["timing"] = {"actual": round(timing["actual_return"], 5), "shifted": timing["shifted_returns"], "p_value": timing["p_value"]}
    if trades:
        out["trade_stats"] = trade_stats(trades)
    return {k: v for k, v in out.items() if v}


__all__ = [
    "build_charts",
    "cost_curve",
    "monthly_returns",
    "returns_histogram",
    "rolling_sharpe",
    "trade_stats",
]
