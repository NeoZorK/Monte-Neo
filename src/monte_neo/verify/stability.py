"""Does the result hold in every stretch of the sample, or did one lucky stretch make it? (context, never changes the verdict)

The per-bar returns of the strategy are cut into equal consecutive windows. The row reports how many
windows made money, the worst and best window, and the Sharpe of each. It complements
``period_consistency`` (calendar years, quarters, months): windows exist for any sample, with or
without timestamps, and show the whole path as a walk-forward would.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from monte_neo.verify.checks import check
from monte_neo.verify.stats import sharpe_per_bar

WINDOWS = 6
MIN_BARS_PER_WINDOW = 50


def rolling_stability(rets: np.ndarray, periods_per_year: float, *, windows: int = WINDOWS) -> dict[str, Any]:
    """Return and Sharpe of each of ``windows`` equal consecutive windows; ``{}`` when the sample is too short."""
    r = np.asarray(rets, dtype=np.float64)
    r = r[np.isfinite(r)]
    if r.size < windows * MIN_BARS_PER_WINDOW:
        return {}
    parts = np.array_split(r, windows)
    scale = math.sqrt(max(float(periods_per_year), 1.0))
    total = [float(np.prod(1.0 + p) - 1.0) for p in parts]
    sharpe = [float(sharpe_per_bar(p)) * scale for p in parts]
    return {
        "windows": int(windows),
        "bars_per_window": int(parts[0].size),
        "returns": [round(v, 5) for v in total],
        "sharpe_annualized": [round(v, 3) for v in sharpe],
        "positive": int(sum(v > 0.0 for v in total)),
        "worst_return": round(min(total), 5),
        "best_return": round(max(total), 5),
    }


def stability_row(info: dict[str, Any]) -> dict[str, Any]:
    """``walk_forward_stability``: how many equal windows of the sample made money (context)."""
    if not info:
        return check("walk_forward_stability", "statistics", "skip", "too few bars to cut into equal windows")
    summary = (
        f"{info['positive']} of {info['windows']} equal windows ({info['bars_per_window']:,} bars each) made money; "
        f"worst {info['worst_return']:+.1%}, best {info['best_return']:+.1%}"
    )
    return check("walk_forward_stability", "statistics", "info", summary, info)


__all__ = ["rolling_stability", "stability_row"]
