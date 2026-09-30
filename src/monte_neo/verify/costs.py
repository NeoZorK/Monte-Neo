"""Cost and execution-timing stress on the fee-aware research-bar engine."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.engine import total_return as _total_return


def breakeven_cost_bps(
    ohlc: dict[str, np.ndarray],
    signals: np.ndarray,
    model: ExecutionModel,
    *,
    max_bps: float = 200.0,
    iterations: int = 14,
) -> dict[str, Any]:
    """Per-side cost (commission, slippage 0) at which total return reaches zero."""

    def at(bps: float) -> float:
        return _total_return(ohlc, signals, replace(model, commission_bps=bps, slippage_bps=0.0, impact_bps=0.0, symbol_costs=()))

    gross = at(0.0)
    if gross <= 0.0:
        return {"breakeven_bps": 0.0, "gross_return": gross, "bounded": True}
    if at(max_bps) > 0.0:
        return {"breakeven_bps": float(max_bps), "gross_return": gross, "bounded": False}
    lo, hi = 0.0, float(max_bps)
    for _ in range(int(iterations)):
        mid = 0.5 * (lo + hi)
        if at(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    return {"breakeven_bps": float(0.5 * (lo + hi)), "gross_return": gross, "bounded": True}


def delay_signals(signals: np.ndarray, delay: int) -> np.ndarray:
    """Shift positions ``delay`` bars later along time (flat while waiting); keeps weights as floats."""
    s = np.asarray(signals)
    s = s if s.dtype.kind == "f" else s.astype(np.int64)
    d = max(0, int(delay))
    if d == 0:
        return s.copy()
    out = np.zeros_like(s)
    if d < s.shape[0]:
        out[d:] = s[:-d]
    return out


def delay_scan(
    ohlc: dict[str, np.ndarray],
    signals: np.ndarray,
    model: ExecutionModel,
    *,
    delays: tuple[int, ...] = (0, 1, 2),
) -> dict[str, Any]:
    """Total return when execution slips by extra bars.

    ``warn`` when a profitable strategy loses everything after one bar of delay:
    the edge then lives in fill timing, which live trading rarely delivers.
    """
    returns = {int(d): _total_return(ohlc, delay_signals(signals, d), model) for d in delays}
    base = returns.get(0, 0.0)
    delayed = returns.get(1)
    fragile = base > 0.0 and delayed is not None and delayed <= 0.0
    return {
        "status": "warn" if fragile else "pass",
        "returns_by_delay": {str(k): v for k, v in returns.items()},
        "fragile_to_one_bar_delay": bool(fragile),
    }


__all__ = ["breakeven_cost_bps", "delay_scan", "delay_signals"]
