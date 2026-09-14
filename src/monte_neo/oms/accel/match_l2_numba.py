"""Numba L2 book walk (CPU parallel reference for Apple Silicon)."""

from __future__ import annotations

import numpy as np
from numba import njit


@njit(cache=True)
def walk_book_market(
    side: int,
    qty: float,
    bid_px: np.ndarray,
    bid_sz: np.ndarray,
    ask_px: np.ndarray,
    ask_sz: np.ndarray,
    commission_bps: float,
    slip_bps: float,
) -> tuple:
    """Return (filled_qty, vwap, fee, n_levels_used)."""
    fee_rate = commission_bps * 1e-4
    slip = slip_bps * 1e-4
    need = qty
    notional = 0.0
    filled = 0.0
    levels = 0
    n = bid_px.shape[0]
    for i in range(n):
        if need <= 1e-15:
            break
        if side > 0:
            px = ask_px[i]
            sz = ask_sz[i]
        else:
            px = bid_px[i]
            sz = bid_sz[i]
        if px <= 0.0 or sz <= 0.0:
            break
        take = need if need < sz else sz
        fill_px = px * (1.0 + float(side) * slip)
        notional += take * fill_px
        filled += take
        need -= take
        levels += 1
    if filled <= 0.0:
        return 0.0, 0.0, 0.0, 0
    vwap = notional / filled
    fee = abs(notional) * fee_rate
    return filled, vwap, fee, levels


@njit(cache=True, parallel=True)
def batch_mid_mark_equity(
    mid: np.ndarray,
    position: float,
    cash0: float,
) -> np.ndarray:
    """Mark-to-mid equity path for a flat position size (stress helper)."""
    n = mid.shape[0]
    eq = np.empty(n, dtype=np.float64)
    for i in range(n):
        eq[i] = cash0 + position * mid[i]
    return eq
