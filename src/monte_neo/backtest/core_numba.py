"""Numba cores for fee-aware next-bar backtests (shared economics)."""

from __future__ import annotations

import numpy as np
from numba import njit

REASON_SIGNAL = 1
REASON_SL = 2
REASON_TP = 3
REASON_FLATTEN = 4


@njit(cache=True)
def run_core_full(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signal: np.ndarray,
    fill_open: bool,
    long_short: bool,
    size_fraction: float,
    commission_bps: float,
    slippage_bps: float,
    initial_cash: float,
    warmup: int,
    sl_pct: float,
    tp_pct: float,
) -> tuple:
    """Full path: equity + trade journal buffers."""
    n = close.shape[0]
    equity = np.empty(n, dtype=np.float64)
    cash = initial_cash
    qty = 0.0
    position = 0
    fill_events = 0
    peak = initial_cash
    max_dd = 0.0
    fee_rate = commission_bps * 1e-4
    slip_rate = slippage_bps * 1e-4
    use_sl = sl_pct > 0.0
    use_tp = tp_pct > 0.0
    entry_px = 0.0
    entry_i = -1
    entry_fees = 0.0
    sl_px = 0.0
    tp_px = 0.0
    te_i = np.empty(n, dtype=np.int64)
    tx_i = np.empty(n, dtype=np.int64)
    te_px = np.empty(n, dtype=np.float64)
    tx_px = np.empty(n, dtype=np.float64)
    t_qty = np.empty(n, dtype=np.float64)
    t_fees = np.empty(n, dtype=np.float64)
    t_reason = np.empty(n, dtype=np.int64)
    n_closed = 0

    for i in range(n):
        mtm = cash + qty * close[i]
        equity[i] = mtm
        if mtm > peak:
            peak = mtm
        dd = (peak - mtm) / peak if peak > 0.0 else 0.0
        if dd > max_dd:
            max_dd = dd

        if position != 0 and qty != 0.0 and (use_sl or use_tp):
            hit = 0
            exit_raw = 0.0
            if position > 0:
                if use_sl and low[i] <= sl_px:
                    hit = REASON_SL
                    exit_raw = sl_px
                elif use_tp and high[i] >= tp_px:
                    hit = REASON_TP
                    exit_raw = tp_px
            else:
                if use_sl and high[i] >= sl_px:
                    hit = REASON_SL
                    exit_raw = sl_px
                elif use_tp and low[i] <= tp_px:
                    hit = REASON_TP
                    exit_raw = tp_px
            if hit != 0:
                exit_px = exit_raw * (1.0 - float(position) * slip_rate)
                proceeds = qty * exit_px
                fee = abs(proceeds) * fee_rate
                cash += proceeds - fee
                fill_events += 1
                te_i[n_closed] = entry_i
                tx_i[n_closed] = i
                te_px[n_closed] = entry_px
                tx_px[n_closed] = exit_px
                t_qty[n_closed] = qty
                t_fees[n_closed] = entry_fees + fee
                t_reason[n_closed] = hit
                n_closed += 1
                qty = 0.0
                position = 0
                entry_fees = 0.0
                equity[i] = cash

        if i < warmup or i + 1 >= n:
            continue

        raw = int(signal[i])
        if long_short:
            target = 1 if raw > 0 else (-1 if raw < 0 else 0)
        else:
            target = 1 if raw > 0 else 0
        if target == position:
            continue

        fill_px = open_[i + 1] if fill_open else close[i + 1]
        if position != 0 and qty != 0.0:
            exit_px = fill_px * (1.0 - float(position) * slip_rate)
            proceeds = qty * exit_px
            fee = abs(proceeds) * fee_rate
            cash += proceeds - fee
            fill_events += 1
            te_i[n_closed] = entry_i
            tx_i[n_closed] = i + 1
            te_px[n_closed] = entry_px
            tx_px[n_closed] = exit_px
            t_qty[n_closed] = qty
            t_fees[n_closed] = entry_fees + fee
            t_reason[n_closed] = REASON_SIGNAL
            n_closed += 1
            qty = 0.0
            position = 0
            entry_fees = 0.0

        if target != 0:
            notional = cash * size_fraction
            entry = fill_px * (1.0 + float(target) * slip_rate)
            if entry <= 0.0:
                continue
            new_qty = (notional / entry) * float(target)
            fee = abs(new_qty * entry) * fee_rate
            cash -= new_qty * entry + fee
            qty = new_qty
            position = target
            fill_events += 1
            entry_px = entry
            entry_i = i + 1
            entry_fees = fee
            if use_sl:
                sl_px = entry * (1.0 - sl_pct * 0.01) if target > 0 else entry * (
                    1.0 + sl_pct * 0.01
                )
            if use_tp:
                tp_px = entry * (1.0 + tp_pct * 0.01) if target > 0 else entry * (
                    1.0 - tp_pct * 0.01
                )

    if position != 0 and qty != 0.0:
        exit_px = close[n - 1] * (1.0 - float(position) * slip_rate)
        proceeds = qty * exit_px
        fee = abs(proceeds) * fee_rate
        cash += proceeds - fee
        fill_events += 1
        te_i[n_closed] = entry_i
        tx_i[n_closed] = n - 1
        te_px[n_closed] = entry_px
        tx_px[n_closed] = exit_px
        t_qty[n_closed] = qty
        t_fees[n_closed] = entry_fees + fee
        t_reason[n_closed] = REASON_FLATTEN
        n_closed += 1
        equity[n - 1] = cash

    return (
        equity,
        cash / initial_cash - 1.0,
        max_dd,
        fill_events,
        cash,
        n_closed,
        te_i,
        tx_i,
        te_px,
        tx_px,
        t_qty,
        t_fees,
        t_reason,
    )


@njit(cache=True)
def run_terminal_return(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signal: np.ndarray,
    fill_open: bool,
    long_short: bool,
    size_fraction: float,
    commission_bps: float,
    slippage_bps: float,
    initial_cash: float,
    warmup: int,
    sl_pct: float,
    tp_pct: float,
) -> float:
    """Lean terminal return (no equity/journal alloc) — same economics."""
    n = close.shape[0]
    cash = initial_cash
    qty = 0.0
    position = 0
    fee_rate = commission_bps * 1e-4
    slip_rate = slippage_bps * 1e-4
    use_sl = sl_pct > 0.0
    use_tp = tp_pct > 0.0
    entry_px = 0.0
    sl_px = 0.0
    tp_px = 0.0

    for i in range(n):
        if position != 0 and qty != 0.0 and (use_sl or use_tp):
            hit = 0
            exit_raw = 0.0
            if position > 0:
                if use_sl and low[i] <= sl_px:
                    hit = 1
                    exit_raw = sl_px
                elif use_tp and high[i] >= tp_px:
                    hit = 1
                    exit_raw = tp_px
            else:
                if use_sl and high[i] >= sl_px:
                    hit = 1
                    exit_raw = sl_px
                elif use_tp and low[i] <= tp_px:
                    hit = 1
                    exit_raw = tp_px
            if hit != 0:
                exit_px = exit_raw * (1.0 - float(position) * slip_rate)
                proceeds = qty * exit_px
                cash += proceeds - abs(proceeds) * fee_rate
                qty = 0.0
                position = 0

        if i < warmup or i + 1 >= n:
            continue
        raw = int(signal[i])
        if long_short:
            target = 1 if raw > 0 else (-1 if raw < 0 else 0)
        else:
            target = 1 if raw > 0 else 0
        if target == position:
            continue
        fill_px = open_[i + 1] if fill_open else close[i + 1]
        if position != 0 and qty != 0.0:
            exit_px = fill_px * (1.0 - float(position) * slip_rate)
            proceeds = qty * exit_px
            cash += proceeds - abs(proceeds) * fee_rate
            qty = 0.0
            position = 0
        if target != 0:
            notional = cash * size_fraction
            entry = fill_px * (1.0 + float(target) * slip_rate)
            if entry <= 0.0:
                continue
            new_qty = (notional / entry) * float(target)
            fee = abs(new_qty * entry) * fee_rate
            cash -= new_qty * entry + fee
            qty = new_qty
            position = target
            entry_px = entry
            if use_sl:
                sl_px = entry * (1.0 - sl_pct * 0.01) if target > 0 else entry * (
                    1.0 + sl_pct * 0.01
                )
            if use_tp:
                tp_px = entry * (1.0 + tp_pct * 0.01) if target > 0 else entry * (
                    1.0 - tp_pct * 0.01
                )

    if position != 0 and qty != 0.0:
        exit_px = close[n - 1] * (1.0 - float(position) * slip_rate)
        proceeds = qty * exit_px
        cash += proceeds - abs(proceeds) * fee_rate
    _ = entry_px
    return cash / initial_cash - 1.0
