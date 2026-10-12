"""Family E: robustness of a score's long-short portfolio (subsets, groups, start dates, CPCV, null, noise).

Every variant is judged on the same net series: top minus bottom quantile, equal weight, weights
decided at ``t - 1`` earn bar ``t``, minus a turnover cost (default 10 bps).
"""

from __future__ import annotations

from typing import Any

from monte_neo.alpha.panel import Panel
from monte_neo.alpha.robustness_common import DEFAULT_COST_BPS
from monte_neo.alpha.robustness_null import (
    bar_construction,
    data_source_replication,
    noise_injection,
    synthetic_market_null,
)
from monte_neo.alpha.robustness_sampling import cpcv_paths, group_split, start_date_sensitivity, universe_subsampling

NEXT_ACTIONS: dict[str, str] = {
    "universe_subsampling": "The edge depends on a few symbols or fails on subsets: check concentration, widen the universe, and remove the names that carry the profit to see what is left.",
    "group_split": "The profit comes from one sector or country: test the score inside the other groups, or restrict the claim to the group where it works.",
    "start_date_sensitivity": "The result changes with the start date: look for a regime or a single episode behind the profit and report results by sub-period.",
    "cpcv_paths": "The net Sharpe is negative on many disjoint periods: the edge is not stable over time; investigate the periods where it fails.",
    "synthetic_market_null": "The score does not beat markets with the same statistics but no score link: the profit may come from market structure or costs, not the signal.",
    "noise_injection": "A little noise destroys the edge: it depends on exact score values; smooth or bucket the score and re-test.",
    "data_source_replication": "The result differs on a second price source: audit the vendors (adjustments, bad prints, survivorship) and trust the cleaner one.",
    "bar_construction": "Profits differ between even and odd bars: the result depends on the bar grid; re-test with other bar offsets or lengths.",
}


def run_robustness(
    panel: Panel,
    quantiles: int = 5,
    horizon: int = 1,
    seed: int = 0,
    groups: dict[str, str] | None = None,
    alt_close: Any = None,
    cost_bps: float = DEFAULT_COST_BPS,
) -> list[dict[str, Any]]:
    """Run family E on the score's long-short portfolio.

    Args:
        panel: The aligned panel.
        quantiles: Quantile buckets (top minus bottom).
        horizon: Label horizon in bars, purged at CPCV block boundaries.
        seed: Seed for subsets, bootstraps and noise.
        groups: Optional ``{symbol: group}`` map (sector, country); E2 is skipped without it.
        alt_close: Optional second price source (T x N array or dates x symbols DataFrame) for E7.
        cost_bps: Cost per unit of weight traded, in basis points.

    Returns:
        Check rows E1..E8 (category ``statistics``).
    """
    return [
        universe_subsampling(panel, quantiles, seed, cost_bps),
        group_split(panel, quantiles, groups, cost_bps),
        start_date_sensitivity(panel, quantiles, cost_bps),
        cpcv_paths(panel, quantiles, horizon, cost_bps),
        synthetic_market_null(panel, quantiles, seed, cost_bps),
        noise_injection(panel, quantiles, seed, cost_bps),
        data_source_replication(panel, quantiles, alt_close, cost_bps),
        bar_construction(panel, quantiles, cost_bps),
    ]


__all__ = ["NEXT_ACTIONS", "run_robustness"]
