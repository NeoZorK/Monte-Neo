"""Are the costs realistic, and how much money can the strategy run? (context checks, never change the verdict)

* **Spread from high and low** (Corwin and Schultz, 2012): the high of a bar is usually a buy at
  the ask and the low a sell at the bid, so two consecutive bars separate the volatility
  component of the high-low range from the spread component. The estimate is noisy for one bar,
  so the median over all bars is used, and it is biased upward when bars are very volatile
  (by a few bps at 0.3% bars, about 15 bps at 1% bars): read it as an order of magnitude next to
  the cost the backtest charged, not as a quote.
* **Capacity**: the largest capital for which the strategy's fills stay within a share of the
  volume traded in the fill bar (1%, 5%, 10%), counting a fill as inside the limit when 90% of
  the fills are. Needs a ``volume`` column; volume is taken in units of the instrument, so the
  traded value of a bar is ``volume x close``.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.checks import check

MIN_BARS = 100
PARTICIPATION = (0.01, 0.05, 0.10)
FILL_QUANTILE = 0.10  # capital at which 90% of the fills are inside the limit
TIGHTEST = 8  # symbols listed for a universe
_K = 3.0 - 2.0 * math.sqrt(2.0)


def corwin_schultz(high: np.ndarray, low: np.ndarray) -> np.ndarray:
    """Per-bar relative spread estimates ``(bars - 1, ...)``; a negative estimate is set to zero."""
    h, lo = np.asarray(high, dtype=np.float64), np.asarray(low, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        hl = np.log(h / lo) ** 2
        beta = hl[:-1] + hl[1:]
        gamma = np.log(np.maximum(h[:-1], h[1:]) / np.minimum(lo[:-1], lo[1:])) ** 2
        alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / _K - np.sqrt(gamma / _K)
        spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    return np.where(np.isfinite(spread), np.maximum(spread, 0.0), np.nan)


def spread_estimate(ohlc: dict[str, np.ndarray], model: ExecutionModel) -> dict[str, Any]:
    """Median high-low spread estimate in bps and the per-side cost the model charged; ``{}`` for too little data."""
    est = corwin_schultz(ohlc["high"], ohlc["low"])
    est = est[np.isfinite(est)]
    if est.size < MIN_BARS:
        return {}
    spread_bps = float(np.median(est) * 1e4)
    return {
        "method": "Corwin-Schultz (2012), median over bars",
        "spread_bps": round(spread_bps, 2),
        "half_spread_bps": round(spread_bps / 2.0, 2),
        "modeled_bps_per_side": round(float(model.mean_side_cost_bps), 2),
        "modeled_slippage_bps": round(float(model.mean_slip_bps), 2),
        "bars": int(est.size),
    }


def spread_row(info: dict[str, Any]) -> dict[str, Any]:
    """``spread_estimate``: the estimated cost of crossing the spread next to the modeled cost (context)."""
    if not info:
        return check("spread_estimate", "economics", "skip", "too few bars to estimate the spread from high and low")
    modeled, half = info["modeled_slippage_bps"], info["half_spread_bps"]
    tail = (
        f"the model charges only {modeled:g} bps slippage per side, well below it: costs may be optimistic"
        if modeled < 0.5 * half
        else f"the model charges {modeled:g} bps slippage per side"
    )
    return check(
        "spread_estimate", "economics", "info",
        f"rough spread estimate from high and low: about {info['spread_bps']:g} bps ({half:g} bps per side); {tail}", info,
    )


def _human(value: float) -> str:
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if value >= size:
            return f"{value / size:.3g}{unit}"
    return f"{value:.3g}"


def capacity(
    ohlc: dict[str, np.ndarray],
    volume: Any,
    traded: np.ndarray,
    model: ExecutionModel,
    symbols: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Capital at which the fills stay within 1%, 5% and 10% of the bar's traded value; ``{}`` without volume or fills.

    One instrument: ``traded`` and ``volume`` are ``(bars,)``. A universe: ``(bars, symbols)`` matrices (``symbols``
    names the columns). Every change of a symbol's weight is an order for that symbol, and it is filled in the next
    bar: the order is ``capital x weight change`` and it must stay within the share of that symbol's traded value
    (``volume x close``). The capacity is the capital at which 90% of all fills, over all symbols, are inside the limit;
    for a universe the symbols with the smallest capacity are listed, because they set the limit.
    """
    if volume is None:
        return {}
    vol = np.asarray(volume, dtype=np.float64)
    close = np.asarray(ohlc["close"], dtype=np.float64)
    weight = np.asarray(traded, dtype=np.float64)
    if vol.shape != close.shape or weight.shape != close.shape or close.ndim not in (1, 2):
        return {}
    if close.ndim == 1:
        vol, close, weight = vol[:, None], close[:, None], weight[:, None]
    weight = weight * float(model.size_fraction * model.fill_fraction * model.leverage)
    change = np.abs(np.diff(weight, axis=0))
    bars, cols = np.nonzero(change > 0.0)
    keep = (bars >= model.warmup_bars) & (bars + 1 < close.shape[0])  # decided at bar t, filled in bar t + 1
    bars, cols = bars[keep], cols[keep]
    dollars = vol * close
    fill_value = dollars[bars + 1, cols]
    ok = np.isfinite(fill_value) & (fill_value > 0.0)
    if not ok.any():
        return {}
    room = fill_value[ok] / change[bars, cols][ok]  # capital that would use all of the bar's volume
    base = float(np.quantile(room, FILL_QUANTILE))
    seen = dollars[np.isfinite(dollars) & (dollars > 0)]
    info: dict[str, Any] = {
        "participation": list(PARTICIPATION),
        "capital": [round(base * p, 2) for p in PARTICIPATION],
        "fills": int(ok.sum()),
        "fills_without_volume": int((~ok).sum()),
        "median_bar_value": round(float(np.median(seen)), 2),
        "share_of_fills_inside": 1.0 - FILL_QUANTILE,
        "assumption": "volume in instrument units; traded value = volume x close",
    }
    if symbols is not None and close.shape[1] > 1 and len(symbols) == close.shape[1]:
        rooms = room
        who = cols[ok]
        rows = []
        for j, name in enumerate(symbols):
            mine = rooms[who == j]
            if mine.size:
                cap = float(np.quantile(mine, FILL_QUANTILE))
                rows.append({"symbol": str(name), "fills": int(mine.size), "capital": [round(cap * p, 2) for p in PARTICIPATION]})
        rows.sort(key=lambda r: r["capital"][1])
        info["symbols"] = int(close.shape[1])
        info["by_symbol"] = rows[:TIGHTEST]
    return info


def capacity_row(info: dict[str, Any]) -> dict[str, Any]:
    """``capacity``: how much capital the strategy can run at a given share of volume (context)."""
    if not info:
        return check("capacity", "economics", "skip", "capacity needs a volume column and at least one fill")
    caps = ", ".join(f"{p:.0%}: {_human(c)}" for p, c in zip(info["participation"], info["capital"], strict=True))
    summary = (
        f"capital that keeps {info['share_of_fills_inside']:.0%} of {info['fills']:,} fills within a share of the bar's volume: {caps} "
        f"(median bar trades {_human(info['median_bar_value'])})"
    )
    tight = [r for r in (info.get("by_symbol") or []) if isinstance(r, dict) and isinstance(r.get("capital"), list) and len(r["capital"]) == 3]
    if tight:
        names = ", ".join(f"{r['symbol']} {_human(r['capital'][1])}" for r in tight[:3])
        summary += f"; tightest of {info.get('symbols', len(tight))} symbols at 5%: {names}"
    return check("capacity", "economics", "info", summary, info)


__all__ = ["capacity", "capacity_row", "corwin_schultz", "spread_estimate", "spread_row"]
