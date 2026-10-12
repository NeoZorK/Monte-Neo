"""Family D on a scores panel: can the top-minus-bottom portfolio of the score actually be traded?

The portfolio is the one family A judges (long the top quantile, short the bottom one, equal weights, rebalanced every
bar). Market impact and participation need an assets-under-management figure (``aum``); without it they are skipped
with that reason, while the capacity curve, short feasibility, holding period and rebalance-day checks still run.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.alpha._core import leg_weights, quantile_index
from monte_neo.alpha.implementability import capacity_curve, market_impact, participation_limit, short_feasibility
from monte_neo.alpha.implementability_timing import rebalance_timing_luck, turnover_vs_decay
from monte_neo.alpha.panel import Panel
from monte_neo.verify.checks import check

NEXT_ACTIONS: dict[str, str] = {
    "market_impact": "Impact at this size eats the edge: trade less often, cap participation, or run less capital.",
    "capacity_curve": "Plan the capital below the AUM where the net Sharpe halves.",
    "short_feasibility": "The short leg sits in illiquid names or pays too much borrow: price borrow from your broker, or drop the short leg and re-test.",
    "participation_limit": "Your trades are a large share of the volume: lower the AUM, add a liquidity filter on past volume, or spread trades over several bars.",
    "turnover_vs_decay": "Trade at the speed of the signal: rebalance less often than the IC half-life, or smooth the score.",
    "rebalance_timing_luck": "The result depends on the day you rebalance: split the portfolio into staggered tranches and judge the average.",
}


def portfolio_weights(panel: Panel, quantiles: int) -> np.ndarray:
    """Long-short weights of the score (top quantile +, bottom quantile -) per date."""
    valid = np.isfinite(panel.scores) & np.isfinite(panel.close)
    return leg_weights(quantile_index(panel.scores, valid, quantiles), quantiles)


def run_implementability(
    panel: Panel, *, quantiles: int, aum: float | None, half_life: float | None, rebalance_every: int = 21
) -> list[dict[str, Any]]:
    """Run family D on the score's long-short portfolio.

    Args:
        panel: The aligned panel.
        quantiles: Quantile buckets (as in family A).
        aum: Capital in the quote currency for impact and participation; ``None`` skips those two.
        half_life: IC half-life in bars from ``ic_decay`` (optional context for the holding period).
        rebalance_every: Rebalance period for the rebalance-day check.

    Returns:
        Check rows (category ``economics``).
    """
    w = portfolio_weights(panel, quantiles)
    close, vol, stamps = panel.close, panel.volume, panel.dates
    rows: list[dict[str, Any]] = []
    if aum is None:
        reason = "no --aum given: market impact and participation need the capital you plan to run"
        rows += [check("market_impact", "economics", "skip", reason, {}), check("participation_limit", "economics", "skip", reason, {})]
    else:
        rows += [market_impact(w, close, vol, stamps, aum), participation_limit(w, close, vol, aum)]
    rows += [
        capacity_curve(w, close, vol, stamps),
        short_feasibility(w, close, vol, stamps),
        turnover_vs_decay(w, half_life),
        rebalance_timing_luck(w, close, stamps, k=rebalance_every),
    ]
    return rows


__all__ = ["NEXT_ACTIONS", "portfolio_weights", "run_implementability"]
