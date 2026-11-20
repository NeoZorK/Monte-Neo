"""Legging risk and short-borrow risk for a pair: what the P&L looks like when the second leg is late or cannot be shorted.

A pairs backtest fills both legs at the same instant. Live, the second leg arrives later (a separate venue, a slower
order path, a rejected short), and for that time the book holds one naked leg. This module re-prices the legs table with
the second and later legs delayed, and with a borrow fee and borrow outages on the short side.

Delay model: a delay of ``d`` bars (``d = k + f``, ``k`` whole bars and ``0 <= f < 1``) makes the quantity a delayed leg
holds over bar ``t`` equal to ``(1 - f) * q[t - k] + f * q[t - k - 1]``, i.e. the fraction ``f`` of a bar still held at
the old quantity. A delay in milliseconds is ``ms / bar_ms`` bars; the default scan is the one the arrival-time module
uses (:data:`monte_neo.verify.arrival.SCAN_MS`). The first leg is assumed to fill on time.

Borrow model: every bar a short quantity ``-q`` pays ``borrow_bps / 1e4 / periods_per_year * q`` (a fee in annual basis
points of the short notional). With ``unavailable_share > 0`` that share of bars (drawn at random, seeded) cannot hold any
short: those bars' short quantities are zero and the long leg stays unhedged.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.legs import rederive

DEFAULT_SCAN_BARS = (0.0, 0.25, 0.5, 1.0, 2.0)
_LEG_PREFIX = "qty_"


def delay_series(q: np.ndarray, delay_bars: float) -> np.ndarray:
    """Quantities seen after a delay of ``delay_bars`` bars (see the module docstring)."""
    if delay_bars < 0:
        raise ValueError("the delay cannot be negative")
    whole, frac = int(delay_bars), float(delay_bars) - int(delay_bars)

    def shifted(k: int) -> np.ndarray:
        if k <= 0:
            return q.copy()
        out = np.empty_like(q)
        out[:k] = q[0]
        out[k:] = q[:-k] if k < q.size else q[0]
        return out

    return (1.0 - frac) * shifted(whole) + frac * shifted(whole + 1)


def _delayed_body(body: pd.DataFrame, delay_bars: float) -> pd.DataFrame:
    """The legs table with every leg after the first one delayed."""
    out = body.copy()
    qty = [c for c in body.columns if c.startswith(_LEG_PREFIX)]
    for col in qty[1:]:
        out[col] = delay_series(body[col].to_numpy(dtype=np.float64), delay_bars)
    return out


def legging_scan(body: pd.DataFrame, delays_bars: tuple[float, ...] = DEFAULT_SCAN_BARS, *, pnl: str = "log") -> list[dict[str, Any]]:
    """Total re-derived P&L with the second leg delayed by each of ``delays_bars``.

    Returns:
        One row per delay: ``delay_bars``, ``total`` (sum of per-bar P&L), ``damage`` (the scan's zero-delay total minus
        this total), ``damage_share`` (damage over the absolute zero-delay total, 0 when that total is 0) and
        ``std_ratio`` (per-bar standard deviation of the delayed P&L over the zero-delay one: the naked-leg risk).
    """
    ref = rederive(body, pnl=pnl)
    base, base_sd = float(ref.sum()), float(ref.std(ddof=1)) or 1e-300
    rows = []
    for d in delays_bars:
        series = ref if d == 0 else rederive(_delayed_body(body, d), pnl=pnl)
        total = float(series.sum())
        share = (base - total) / abs(base) if base != 0.0 else 0.0
        rows.append({"delay_bars": float(d), "total": total, "damage": base - total, "damage_share": share, "std_ratio": float(series.std(ddof=1)) / base_sd})
    return rows


def borrow_scenario(
    body: pd.DataFrame, *, borrow_bps: float = 0.0, unavailable_share: float = 0.0, periods_per_year: float = 252.0,
    pnl: str = "log", seed: int = 7,
) -> dict[str, Any]:
    """P&L with a borrow fee on the short quantities and a share of bars where no short can be held.

    Returns:
        ``base_total``, ``total``, ``fee`` (total fees paid), ``outage_loss`` (change of the P&L caused by the outages
        alone, fee excluded), ``damage_share`` and the inputs.
    """
    if borrow_bps < 0 or not 0.0 <= unavailable_share <= 1.0:
        raise ValueError("borrow_bps must be >= 0 and unavailable_share between 0 and 1")
    base = float(rederive(body, pnl=pnl).sum())
    out = body.copy()
    qty = [c for c in body.columns if c.startswith(_LEG_PREFIX)]
    blocked = np.random.default_rng(seed).random(len(body)) < unavailable_share
    for col in qty:
        q = body[col].to_numpy(dtype=np.float64)
        out[col] = np.where(blocked & (q < 0.0), 0.0, q)
    held = float(rederive(out, pnl=pnl).sum())
    short = sum(np.clip(-out[c].to_numpy(dtype=np.float64)[1:], 0.0, None) for c in qty)
    fee = float(np.sum(short) * borrow_bps / 1e4 / max(periods_per_year, 1.0))
    total = held - fee
    return {
        "base_total": base, "total": total, "fee": fee, "outage_loss": base - held,
        "damage_share": (base - total) / abs(base) if base != 0.0 else 0.0,
        "borrow_bps": float(borrow_bps), "unavailable_share": float(unavailable_share), "blocked_bars": int(blocked.sum()),
    }


__all__ = ["DEFAULT_SCAN_BARS", "borrow_scenario", "delay_series", "legging_scan"]
