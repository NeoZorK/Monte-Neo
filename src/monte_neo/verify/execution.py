"""Execution with a volume limit, partial fills and square-root impact (one instrument, target weights).

Each bar the strategy wants to move from the weight it holds to ``target``. The trade is capped at ``max_participation``
of the bar's traded value (``volume * close``); the unfilled remainder stays wanted and is traded in later bars, so a
big order is *spread*, not lost. Each fill pays ``fee_bps`` plus a market-impact cost from the square-root law
``impact = coef * sigma * sqrt(Q / V)`` (Almgren, Thum, Hauptmann and Li 2005, "Direct estimation of equity market
impact", Risk 18(7); Toth et al. 2011, Phys. Rev. X 1), with ``sigma`` the bar volatility and ``Q / V`` the fill's share
of the bar's volume. ``coef`` defaults to 1.0, the order of magnitude found empirically; replace it with your own estimate.

The returned row compares the result with the frictionless-fill return of the same targets: ``warn`` when the capital
cannot be traded at this participation without losing a large part of the return (see :func:`execution_row`).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.verify.checks import check
from monte_neo.verify.execution_calib import decay_factor

LOSS_WARN = 0.25  # share of the ideal return lost to partial fills and impact that triggers a warning
LAG_WARN = 0.10  # mean share of the wanted position that is not held


def simulate_execution(
    target: np.ndarray, close: np.ndarray, volume: np.ndarray, *, capital: float, max_participation: float = 0.1,
    fee_bps: float = 5.0, impact_coef: float = 1.0, vol_window: int = 20, decay_half_life_bars: float | None = None,
) -> dict[str, Any]:
    """Run the volume-capped execution; ``held[t]`` is the weight held over bar ``t+1`` (decided at the close of ``t``).

    ``decay_half_life_bars`` (default ``None``: each fill's impact is paid once) adds transient impact: the displacement
    of earlier fills decays with that half-life and a later fill in the same direction pays on top of what is left
    (opposite-direction fills never earn it back: the cost is floored at the plain impact). Calibrate ``impact_coef``
    from your fills with :func:`monte_neo.verify.execution_calib.calibrate_impact`.

    Raises:
        ValueError: Bad capital, participation outside (0, 1], negative costs or arrays of different lengths.
    """
    t, c, v = (np.asarray(x, dtype=np.float64) for x in (target, close, volume))
    if not (t.size == c.size == v.size) or t.size < 3:
        raise ValueError("target, close and volume must have the same length (at least 3 bars)")
    if capital <= 0 or not 0 < max_participation <= 1 or fee_bps < 0 or impact_coef < 0:
        raise ValueError("capital > 0, 0 < max_participation <= 1, fee_bps >= 0 and impact_coef >= 0 are required")
    ret = np.zeros(c.size)
    ret[1:] = c[1:] / c[:-1] - 1.0
    sigma = np.sqrt(np.maximum(_rolling_var(ret, vol_window), 0.0))
    cap_w = max_participation * np.nan_to_num(v * c) / capital  # tradable weight change per bar
    held = np.zeros(c.size)
    cost = np.zeros(c.size)
    prev = 0.0
    lam = decay_factor(decay_half_life_bars) if decay_half_life_bars is not None else 0.0
    resid = 0.0  # signed displacement left by earlier fills (fraction of price)
    for i in range(c.size):
        step = float(np.clip(t[i] - prev, -cap_w[i], cap_w[i]))
        share = abs(step) * capital / max(float(v[i] * c[i]), 1e-12)  # fill's share of the bar's traded value
        impact = impact_coef * sigma[i] * np.sqrt(min(share, 1.0))
        resid = lam * resid  # one bar of decay
        extra = max(0.0, float(np.sign(step)) * resid)
        cost[i] = abs(step) * (fee_bps / 1e4 + impact + extra)
        resid += float(np.sign(step)) * impact
        prev += step
        held[i] = prev
    pnl = np.zeros(c.size)
    pnl[1:] = held[:-1] * ret[1:] - cost[1:]
    ideal = np.zeros(c.size)
    ideal[1:] = t[:-1] * ret[1:] - np.abs(np.diff(t, prepend=0.0))[1:] * fee_bps / 1e4
    gap = np.abs(t - held)
    return {
        "held": held, "pnl": pnl, "ideal_pnl": ideal, "cost": cost,
        "total_return": float(np.prod(1.0 + pnl) - 1.0), "ideal_return": float(np.prod(1.0 + ideal) - 1.0),
        "mean_position_gap": float(np.mean(gap)), "mean_fill_ratio": _fill_ratio(t, held),
        "max_share_of_volume": float(np.max(np.abs(np.diff(held, prepend=0.0)) * capital / np.maximum(v * c, 1e-12))),
    }


def _rolling_var(x: np.ndarray, window: int) -> np.ndarray:
    csum = np.cumsum(np.insert(x, 0, 0.0))
    csq = np.cumsum(np.insert(x * x, 0, 0.0))
    idx = np.arange(1, x.size + 1)
    lo = np.maximum(idx - window, 0)
    n = idx - lo
    mean = (csum[idx] - csum[lo]) / n
    return (csq[idx] - csq[lo]) / n - mean * mean


def _fill_ratio(target: np.ndarray, held: np.ndarray) -> float:
    wanted = float(np.sum(np.abs(np.diff(target, prepend=0.0))))
    return float(np.sum(np.abs(np.diff(held, prepend=0.0))) / wanted) if wanted > 0 else 1.0


def execution_row(
    target: np.ndarray, close: np.ndarray, volume: np.ndarray, *, capital: float, max_participation: float = 0.1,
    fee_bps: float = 5.0, impact_coef: float = 1.0,
) -> dict[str, Any]:
    """Check row ``execution_capacity``: what the strategy returns when it must trade within a share of the volume.

    ``warn`` when more than 25 % of the frictionless return is lost, or the held weight lags the wanted one by over 10 %
    on average; ``skip`` when the frictionless return is not positive.
    """
    r = simulate_execution(target, close, volume, capital=capital, max_participation=max_participation,
                           fee_bps=fee_bps, impact_coef=impact_coef)
    det = {k: r[k] for k in ("total_return", "ideal_return", "mean_position_gap", "mean_fill_ratio", "max_share_of_volume")}
    det.update(capital=float(capital), max_participation=float(max_participation))
    if r["ideal_return"] <= 0.0:
        return check("execution_capacity", "economics", "skip", "not profitable at frictionless fills", det)
    lost = 1.0 - r["total_return"] / r["ideal_return"]
    text = (f"at {max_participation:.0%} of volume and capital {capital:,.0f}: return {r['total_return']:+.1%} vs "
            f"{r['ideal_return']:+.1%} frictionless ({lost:.0%} lost), position lags the target by {r['mean_position_gap']:.1%} on average")
    if lost > LOSS_WARN or r["mean_position_gap"] > LAG_WARN:
        return check("execution_capacity", "economics", "warn", "the strategy does not trade cleanly at this size: " + text, det)
    return check("execution_capacity", "economics", "pass", text, det)


__all__ = ["LAG_WARN", "LOSS_WARN", "execution_row", "simulate_execution"]
