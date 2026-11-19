"""Funding on the perpetual legs of a long-short portfolio, and capacity on a stated AUM grid.

A short perpetual leg earns or pays the real funding of its symbol, a long leg the opposite; pricing the short side with a
constant (or nothing) makes it too cheap in the months when funding is large. The history is an input
(``timestamp, symbol, funding_bps`` = what a long pays per bar, negative when the long receives) and enters the same net
series as commissions and impact, so the capacity gate reads net-of-funding numbers.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.alpha.implementability import _net_series, _prep
from monte_neo.alpha.implementability_common import ann_return, ann_sharpe, gross_series, has_volume, periods_per_year
from monte_neo.alpha.panel import Panel, _frame, _normalise
from monte_neo.verify.checks import check

CATEGORY = "economics"
MIN_COVERAGE = 0.8
DRAG_WARN_SHARE = 0.5


def load_funding(source: Any, panel: Panel) -> np.ndarray:
    """Funding (bps per bar a long pays) aligned to the panel; a symbol-date without a quote is NaN.

    Raises:
        ValueError: A symbol that is not in the panel, or duplicated (timestamp, symbol) rows (refused when the table is read).
    """
    table = _normalise(_frame(source), "funding_bps")
    unknown = sorted(set(table["symbol"]) - set(panel.symbols))
    if unknown:
        raise ValueError(f"funding has symbols that are not in the prices: {', '.join(unknown[:5])}")
    wide = table.pivot(index="timestamp", columns="symbol", values="funding_bps")
    return wide.reindex(index=panel.dates, columns=panel.symbols).to_numpy(dtype=np.float64)


def funding_drag(w: np.ndarray, funding_bps: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Per-bar funding cost of the held weights (positive = cost), its short-leg part, and the share of held positions with a quote."""
    f = np.nan_to_num(funding_bps, nan=0.0) / 1e4
    held = np.abs(np.vstack([np.zeros((1, w.shape[1])), w[:-1]])) > 0
    cov = float(np.isfinite(funding_bps)[held].mean()) if held.any() else 1.0
    return gross_series(w, f), gross_series(np.minimum(w, 0.0), f), cov


def funding_drag_row(weights: Any, close: Any, timestamps: Any, funding_bps: np.ndarray | None) -> dict[str, Any]:
    """Check row ``funding_drag``: net return after the real funding of every leg; the short legs are reported apart."""
    if funding_bps is None:
        return check("funding_drag", CATEGORY, "skip", "no funding history given: perpetual funding on the short legs is not priced", {"reason": "no_funding"})
    from monte_neo.alpha.implementability_common import as_2d, clean_weights, simple_returns

    w, c = clean_weights(weights), as_2d(close)
    ppy = periods_per_year(timestamps)
    gross = gross_series(w, simple_returns(c))
    drag, short, cov = funding_drag(w, funding_bps)
    g, d, s = ann_return(gross, ppy), ann_return(drag, ppy), ann_return(short, ppy)
    net = g - d
    share = d / g if g > 0 and d > 0 else None
    if net <= 0.0 and g > 0.0:
        status = "fail"
    elif cov < MIN_COVERAGE or (share is not None and share > DRAG_WARN_SHARE):
        status = "warn"
    else:
        status = "pass"
    details = {"gross_annual_return": g, "funding_annual_cost": d, "short_legs_annual_cost": s, "net_annual_return": net, "funding_share_of_gross": share,
               "coverage": cov, "net_sharpe": ann_sharpe(gross - drag, ppy)}
    note = f"; funding history covers only {cov:.0%} of the held positions" if cov < MIN_COVERAGE else ""
    return check("funding_drag", CATEGORY, status, f"gross {g:.2%}, real funding {d:+.2%} (short legs {s:+.2%}), net {net:.2%} per year{note}", details)


def capacity_grid_row(weights: Any, close: Any, volume: Any, timestamps: Any, aum_grid: list[float] | None, min_capacity: float | None,
                      funding_bps: np.ndarray | None = None, impact_coef: float = 1.0, commission_bps: float = 1.0) -> dict[str, Any]:
    """Check row ``capacity_grid``: net Sharpe and return at each stated AUM (after impact, commission and funding), and a gate.

    The gate is met when the net annual return is positive at ``min_capacity`` (default: the largest AUM of the grid).
    """
    if not aum_grid:
        return check("capacity_grid", CATEGORY, "skip", "no AUM grid given (--aum-grid)", {"reason": "no_grid"})
    if not has_volume(volume):
        return check("capacity_grid", CATEGORY, "skip", "volume is missing: capacity cannot be estimated", {"reason": "no_volume"})
    grid = sorted(float(a) for a in aum_grid)
    if grid[0] <= 0:
        raise ValueError("every AUM in the grid must be positive")
    gate = float(min_capacity) if min_capacity is not None else grid[-1]
    w, c, v = _prep(weights, close, volume)
    ppy = periods_per_year(timestamps)
    drag = funding_drag(w, funding_bps)[0] if funding_bps is not None else 0.0

    def point(aum: float) -> dict[str, float]:
        gross, comm, imp = _net_series(w, c, v, aum, impact_coef, commission_bps)
        net = gross - comm - imp - drag
        return {"aum": aum, "net_sharpe": ann_sharpe(net, ppy), "net_annual_return": ann_return(net, ppy)}

    rows = [point(a) for a in sorted({*grid, gate})]
    at_gate = next(p for p in rows if p["aum"] == gate)
    ok = at_gate["net_annual_return"] > 0.0
    summary = f"net Sharpe at {gate:,.0f}: {at_gate['net_sharpe']:.2f} ({at_gate['net_annual_return']:.2%} a year); gate {'met' if ok else 'not met'}"
    return check("capacity_grid", CATEGORY, "pass" if ok else "fail", summary, {"grid": rows, "gate_aum": gate, "with_funding": funding_bps is not None})


__all__ = ["capacity_grid_row", "funding_drag", "funding_drag_row", "load_funding"]
