"""Returns of the executable portfolio after costs, and the level-3 and level-6 evidence that is read from them.

A cross-sectional score can predict returns (IC, quantile spread) and still earn nothing once its portfolio pays for trading. The
multiple-testing numbers (Harvey-Liu-Zhu t, minimum backtest length, Deflated Sharpe) and the cost sensitivity are therefore computed on the
**net** returns of the top-minus-bottom portfolio: gross return minus commission, square-root market impact at the stated AUM (when volume
is known) and the real funding of every leg (when a funding history is given). Without ``aum`` or volume only commission is charged and the
rows say so. Signal significance belongs to ARL level 4; surviving the search (level 6) is judged on what the portfolio earns.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.alpha.funding_cost import funding_drag
from monte_neo.alpha.implementability import _net_series
from monte_neo.alpha.implementability_common import (
    ann_return,
    as_2d,
    clean_weights,
    gross_series,
    has_volume,
    simple_returns,
    weight_changes,
)
from monte_neo.verify.checks import check
from monte_neo.verify.stats import deflated_sharpe

COMMISSION_BPS = 1.0
IMPACT_COEF = 1.0


def executable_returns(weights: Any, close: Any, volume: Any, aum: float | None, *, cost_multiple: float = 1.0,
                       funding_bps: np.ndarray | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    """Net per-bar returns of the portfolio and what was charged (``info["costs"]``)."""
    w, c = clean_weights(weights), as_2d(close)
    if aum is not None and has_volume(volume):
        gross, comm, imp = _net_series(w, c, as_2d(volume), float(aum), IMPACT_COEF, COMMISSION_BPS)
        costs = f"commission {COMMISSION_BPS:g} bp and square-root impact at AUM {aum:.3g}"
    else:
        gross = gross_series(w, simple_returns(c))
        comm = np.abs(weight_changes(w)).sum(axis=1) * COMMISSION_BPS / 1e4
        imp = np.zeros_like(gross)
        costs = f"commission {COMMISSION_BPS:g} bp only (no --aum or no volume: market impact is not included)"
    net = gross - cost_multiple * (comm + imp)
    if funding_bps is not None:
        net = net - funding_drag(w, funding_bps)[0]
        costs += " and the real funding of every leg"
    return net, {"costs": costs, "cost_multiple": cost_multiple, "gross_annual": None}


def cost_sensitivity_row(weights: Any, close: Any, volume: Any, aum: float | None, ppy: float, funding_bps: np.ndarray | None = None) -> dict[str, Any]:
    """Row ``cost_sensitivity``: the portfolio's net annual return at the modelled costs and at twice them.

    ``fail`` when it does not earn at the modelled costs, ``warn`` when it earns but not at double, ``pass`` otherwise.
    """
    one, info = executable_returns(weights, close, volume, aum, funding_bps=funding_bps)
    two, _ = executable_returns(weights, close, volume, aum, cost_multiple=2.0, funding_bps=funding_bps)
    a1, a2 = ann_return(one, ppy), ann_return(two, ppy)
    details = {"net_annual_return_1x": a1, "net_annual_return_2x": a2, "costs": info["costs"]}
    text = f"net return {a1:+.1%} a year at the modelled costs, {a2:+.1%} at double ({info['costs']})"
    if a1 <= 0.0:
        return check("cost_sensitivity", "economics", "fail", "the portfolio does not earn after costs: " + text, details)
    if a2 <= 0.0:
        return check("cost_sensitivity", "economics", "warn", "the edge does not survive doubled costs: " + text, details)
    return check("cost_sensitivity", "economics", "pass", text, details)


def net_deflated_sharpe_row(net: np.ndarray, n_trials: int, ppy: float, costs: str) -> dict[str, Any]:
    """Row ``deflated_sharpe`` on the net returns of the portfolio with the project's ``n_trials``."""
    d = deflated_sharpe(net, n_trials=int(n_trials), periods_per_year=ppy)
    v = float(d["deflated_sharpe"])
    status = "pass" if v >= 0.95 else ("warn" if v >= 0.5 else "fail")
    summary = f"deflated Sharpe {v:.3f} over {d['n_trials']} trial(s) on net returns (Sharpe {d['sharpe_annualized']:.2f} a year after {costs})"
    return check("deflated_sharpe", "statistics", status, summary, {**d, "returns": "net of costs", "costs": costs})


__all__ = ["cost_sensitivity_row", "executable_returns", "net_deflated_sharpe_row"]
