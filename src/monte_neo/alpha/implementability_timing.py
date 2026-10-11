"""Family D checks on trading frequency and timing: D3, D6, D7."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.alpha.implementability_common import (
    ann_return,
    as_2d,
    clean_weights,
    gross_series,
    periods_per_year,
    simple_returns,
    weight_changes,
)
from monte_neo.verify.checks import check

CATEGORY = "economics"
TIMING_EPS = 1e-4
EXEC_DROP = 0.5


def turnover_vs_decay(weights: Any, half_life_bars: float | None = None) -> dict[str, Any]:
    """Average holding period (from turnover) versus the signal half-life.

    Holding period = ``2 * mean gross exposure / mean traded weight`` per bar (a full
    flip every bar is one bar). Info only.

    Args:
        weights: (T, N) target weights.
        half_life_bars: Signal half-life in bars (from the IC decay), optional.
    """
    w = clean_weights(weights)
    traded = float(np.abs(weight_changes(w)).sum(axis=1).mean())
    gross = float(np.abs(w).sum(axis=1).mean())
    hold = 2.0 * gross / traded if traded > 1e-12 else float("inf")
    details: dict[str, Any] = {"holding_bars": hold, "turnover_per_bar": traded, "half_life_bars": half_life_bars}
    if not np.isfinite(hold):
        return check("turnover_vs_decay", CATEGORY, "info", "the portfolio never trades", details)
    summary = f"holding {hold:.1f} bars"
    if half_life_bars and half_life_bars > 0:
        ratio = half_life_bars / hold
        details["trade_ratio"] = ratio
        summary += f", signal half-life {half_life_bars:.1f} bars: "
        summary += f"you trade {ratio:.1f}x more than the signal needs" if ratio > 1.2 else (
            f"you hold {1 / ratio:.1f}x longer than the signal lasts" if ratio < 1 / 1.2 else "holding matches the signal"
        )
    return check("turnover_vs_decay", CATEGORY, "info", summary, details)


def held_weights(weights: np.ndarray, k: int, offset: int) -> np.ndarray:
    """Weights rebalanced on bars ``offset, offset + k, ...`` and held in between (zero before the first)."""
    t = np.arange(weights.shape[0])
    last = t - ((t - offset) % k)
    out = weights[np.clip(last, 0, None)].copy()
    out[last < 0] = 0.0
    return out


def tranche_weights(weights: Any, k: int, n_tranches: int) -> np.ndarray:
    """Average of ``n_tranches`` sleeves rebalancing every ``k`` bars on staggered offsets.

    Args:
        weights: (T, N) daily target weights.
        k: Rebalance period in bars.
        n_tranches: Number of staggered sleeves (offsets spread evenly over ``k``).

    Returns:
        (T, N) blended target weights.
    """
    w = clean_weights(weights)
    offsets = [int(i * k // n_tranches) for i in range(n_tranches)]
    return np.mean([held_weights(w, k, o) for o in offsets], axis=0)


def _net(w: np.ndarray, ret: np.ndarray, cost_bps: float) -> np.ndarray:
    return gross_series(w, ret) - np.abs(weight_changes(w)).sum(axis=1) * cost_bps / 1e4


def rebalance_timing_luck(
    weights: Any, close: Any, timestamps: Any, k: int = 21, cost_bps: float = 10.0
) -> dict[str, Any]:
    """Does the result depend on which day of the cycle you rebalance?

    Builds ``k`` variants rebalancing on offsets ``0..k-1``, holding weights in between,
    and reports the annualised net return of each. Warns if ``max - min`` exceeds
    ``max(|median|, 1e-4)``.
    """
    w, ret = clean_weights(weights), simple_returns(as_2d(close))
    if k < 2 or w.shape[0] < 2 * k:
        return check("rebalance_timing_luck", CATEGORY, "skip", "sample too short for rebalance offsets", {"k": k})
    ppy = periods_per_year(timestamps)
    vals = [ann_return(_net(held_weights(w, k, o), ret, cost_bps), ppy) for o in range(k)]
    lo, med, hi = float(np.min(vals)), float(np.median(vals)), float(np.max(vals))
    spread = hi - lo
    # Offsets differ by noise too: the spread must also exceed two standard errors of one offset's annual return.
    base = _net(held_weights(w, k, 0), ret, cost_bps)
    se = float(np.std(base) * ppy / np.sqrt(max(len(base), 1)))
    # Zoo A15: honest twins stay below 1.3x the median, traps above 6.9x; noise also has to be beaten.
    status = "warn" if spread > max(2.0 * abs(med), TIMING_EPS) and spread > 2.0 * se else "pass"
    summary = f"annual net return by rebalance day: min {lo:.2%}, median {med:.2%}, max {hi:.2%} (k={k})"
    details = {"k": k, "cost_bps": cost_bps, "values": vals, "min": lo, "median": med, "max": hi, "spread": spread, "std": float(np.std(vals)), "noise_se": se}
    return check("rebalance_timing_luck", CATEGORY, status, summary, details)


def execution_price_sensitivity(
    weights: Any, open_: Any, close: Any, timestamps: Any, commission_bps: float = 0.0
) -> dict[str, Any]:
    """Same weights filled at the next close, next open or their midpoint.

    Weights decided on bar ``t`` are filled at price ``f[t+1]`` and held to ``f[t+2]``
    for ``f`` in close, open and ``(open + close) / 2``. Warns if the sign of the annual
    return changes or the result drops by more than 50 % versus the next close.
    """
    w, o, c = clean_weights(weights), as_2d(open_), as_2d(close)
    ppy = periods_per_year(timestamps)
    held2 = np.vstack([np.zeros((1, w.shape[1])), w[:-1]])
    cost = np.abs(weight_changes(w)).sum(axis=1) * commission_bps / 1e4
    res = {}
    for name, px in (("next_close", c), ("next_open", o), ("mid", (o + c) / 2.0)):
        res[name] = ann_return((held2[:-1] * simple_returns(px)[1:]).sum(axis=1) - cost[1:], ppy)
    base = res["next_close"]
    others = [res["next_open"], res["mid"]]
    flip = any(np.sign(x) != np.sign(base) for x in others if abs(x) > 1e-12) or (base > 0 and min(others) < 0)
    drop = base > 0 and min(others) < (1.0 - EXEC_DROP) * base
    status = "warn" if flip or drop else "pass"
    summary = ", ".join(f"{k} {v:.2%}" for k, v in res.items()) + " annual return"
    return check("execution_price_sensitivity", CATEGORY, status, summary, {**res, "sign_change": bool(flip)})
