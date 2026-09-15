"""Numba-accelerated OMS helpers (CPU reference / M1 Pro parallel path)."""

from __future__ import annotations

import numpy as np
from numba import njit, prange


@njit(cache=True)
def batch_terminal_long_flat(
    open_: np.ndarray,
    close: np.ndarray,
    signals: np.ndarray,
    commission_bps: float,
    slip_bps: float,
    initial_cash: float,
    size_fraction: float,
    warmup: int,
) -> np.ndarray:
    """Fast long/flat next-bar-open path for many signal rows (OMS-aligned costs).

    Used as CPU reference and bulk research bridge; full OMS event loop stays
    in Python for order lifecycle honesty.
    """
    n_combo = signals.shape[0]
    n = close.shape[0]
    out = np.empty(n_combo, dtype=np.float64)
    fee_rate = commission_bps * 1e-4
    slip_rate = slip_bps * 1e-4
    for j in prange(n_combo):
        cash = initial_cash
        qty = 0.0
        position = 0
        for i in range(n):
            if i < warmup or i + 1 >= n:
                continue
            target = 1 if signals[j, i] > 0 else 0
            if target == position:
                continue
            fill_px = open_[i + 1]
            if position != 0 and qty != 0.0:
                exit_px = fill_px * (1.0 - slip_rate)
                proceeds = qty * exit_px
                fee = abs(proceeds) * fee_rate
                cash += proceeds - fee
                qty = 0.0
                position = 0
            if target != 0:
                notional = cash * size_fraction
                entry = fill_px * (1.0 + slip_rate)
                if entry <= 0.0 or notional <= 0.0:
                    continue
                qty = notional / entry
                fee = abs(qty * entry) * fee_rate
                cash -= qty * entry + fee
                position = 1
        if position != 0 and qty != 0.0:
            exit_px = close[n - 1] * (1.0 - slip_rate)
            proceeds = qty * exit_px
            fee = abs(proceeds) * fee_rate
            cash += proceeds - fee
        out[j] = cash / initial_cash - 1.0
    return out
