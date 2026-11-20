"""Liquidity stress: the same targets traded in a dry market.

The scenario cuts the volume of every bar to ``volume_keep`` of its value (default 30 %), raises the market-impact
coefficient by ``impact_mult`` (default 3x) and adds ``spread_bps`` of extra cost per side (default 5 bps), then runs
:func:`monte_neo.verify.execution.simulate_execution` on the unchanged targets. March 2020 and May 2021 showed
volumes and depth falling while spreads widened several-fold (see Brunnermeier and Pedersen 2009, "Market liquidity
and funding liquidity", Review of Financial Studies 22(6)). The row warns when the stressed return is below zero while
the normal one is positive, or when over half of the normal return is lost.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.verify.checks import check
from monte_neo.verify.execution import simulate_execution

LOSS_WARN = 0.5


def liquidity_stress(
    target: np.ndarray, close: np.ndarray, volume: np.ndarray, *, capital: float, max_participation: float = 0.1,
    fee_bps: float = 5.0, impact_coef: float = 1.0, volume_keep: float = 0.3, impact_mult: float = 3.0, spread_bps: float = 5.0,
) -> dict[str, Any]:
    """Normal and dry-market returns of the same targets.

    Raises:
        ValueError: ``volume_keep`` outside (0, 1], ``impact_mult`` below 1 or negative ``spread_bps``.
    """
    if not 0.0 < volume_keep <= 1.0 or impact_mult < 1.0 or spread_bps < 0.0:
        raise ValueError("volume_keep in (0, 1], impact_mult >= 1 and spread_bps >= 0 are required")
    kw = {"capital": capital, "max_participation": max_participation}
    base = simulate_execution(target, close, volume, fee_bps=fee_bps, impact_coef=impact_coef, **kw)
    dry = simulate_execution(target, close, np.asarray(volume, dtype=np.float64) * volume_keep, fee_bps=fee_bps + spread_bps,
                             impact_coef=impact_coef * impact_mult, **kw)
    return {"normal_return": base["total_return"], "stressed_return": dry["total_return"], "ideal_return": base["ideal_return"],
            "stressed_fill_ratio": dry["mean_fill_ratio"], "normal_fill_ratio": base["mean_fill_ratio"],
            "volume_keep": volume_keep, "impact_mult": impact_mult, "spread_bps": spread_bps}


def liquidity_stress_row(res: dict[str, Any]) -> dict[str, Any]:
    """``liquidity_stress``: see the module docstring for the rule."""
    n, s = res["normal_return"], res["stressed_return"]
    if n <= 0.0:
        return check("liquidity_stress", "economics", "skip", "not profitable at normal liquidity", res)
    text = (f"return {n:+.1%} normally, {s:+.1%} with {res['volume_keep']:.0%} of the volume, impact x{res['impact_mult']:g} and "
            f"+{res['spread_bps']:g} bps per side; fills reach {res['stressed_fill_ratio']:.0%} of the wanted trades")
    if s < 0.0 or (n - s) / n > LOSS_WARN:
        return check("liquidity_stress", "economics", "warn", "a dry market takes the profit: " + text, res)
    return check("liquidity_stress", "economics", "pass", text, res)


__all__ = ["LOSS_WARN", "liquidity_stress", "liquidity_stress_row"]
