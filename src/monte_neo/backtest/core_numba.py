"""Numba cores for fee-aware next-bar backtests (shared economics)."""

from __future__ import annotations

import numpy as np
from numba import njit

REASON_SIGNAL = 1
REASON_SL = 2
REASON_TP = 3
REASON_FLATTEN = 4
REASON_TRAIL = 5


@njit(cache=True)
def _stop_hit(
    position: int,
    high: float,
    low: float,
    use_sl: bool,
    use_tp: bool,
    use_trail: bool,
    sl_px: float,
    tp_px: float,
    peak_px: float,
    trail_pct: float,
) -> tuple:
    """Return (hit_reason, exit_raw, new_sl_px, new_peak_px). hit_reason 0 = none."""
    if position > 0:
        peak = peak_px
        stop = sl_px
        if use_trail and high > peak:
            peak = high
            trail_stop = peak * (1.0 - trail_pct * 0.01)
            if (not use_sl) or trail_stop > stop:
                stop = trail_stop
        if (use_sl or use_trail) and low <= stop:
            reason = REASON_TRAIL if (use_trail and stop != sl_px) else REASON_SL
            if use_trail and not use_sl:
                reason = REASON_TRAIL
            return reason, stop, stop, peak
        if use_tp and high >= tp_px:
            return REASON_TP, tp_px, stop, peak
        return 0, 0.0, stop, peak
    peak = peak_px
    stop = sl_px
    if use_trail and low < peak:
        peak = low
        trail_stop = peak * (1.0 + trail_pct * 0.01)
        if (not use_sl) or trail_stop < stop:
            stop = trail_stop
    if (use_sl or use_trail) and high >= stop:
        reason = REASON_TRAIL if (use_trail and stop != sl_px) else REASON_SL
        if use_trail and not use_sl:
            reason = REASON_TRAIL
        return reason, stop, stop, peak
    if use_tp and low <= tp_px:
        return REASON_TP, tp_px, stop, peak
    return 0, 0.0, stop, peak


@njit(cache=True)
def run_core_full(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signal: np.ndarray,
    session_ok: np.ndarray,
    fill_open: bool,
    long_short: bool,
    size_fraction: float,
    commission_bps: float,
    slip_bps: float,
    initial_cash: float,
    warmup: int,
    sl_pct: float,
    tp_pct: float,
    trail_pct: float,
    fill_fraction: float,
    leverage: float,
    funding_bps: float,
) -> tuple:
    """Full path: equity + journal (SL/TP/trail/partial/funding/leverage/session)."""
    n = close.shape[0]
    equity = np.empty(n, dtype=np.float64)
    cash = initial_cash
    qty = 0.0
    position = 0
    fill_events = 0
    peak_eq = initial_cash
    max_dd = 0.0
    fee_rate = commission_bps * 1e-4
    slip_rate = slip_bps * 1e-4
    fund_rate = funding_bps * 1e-4
    use_sl = sl_pct > 0.0
    use_tp = tp_pct > 0.0
    use_trail = trail_pct > 0.0
    entry_px = 0.0
    entry_i = -1
    entry_fees = 0.0
    sl_px = 0.0
    tp_px = 0.0
    peak_px = 0.0
    te_i = np.empty(n, dtype=np.int64)
    tx_i = np.empty(n, dtype=np.int64)
    te_px = np.empty(n, dtype=np.float64)
    tx_px = np.empty(n, dtype=np.float64)
    t_qty = np.empty(n, dtype=np.float64)
    t_fees = np.empty(n, dtype=np.float64)
    t_reason = np.empty(n, dtype=np.int64)
    n_closed = 0

    for i in range(n):
        if position != 0 and qty != 0.0 and fund_rate > 0.0:
            cash -= abs(qty * close[i]) * fund_rate
        mtm = cash + qty * close[i]
        equity[i] = mtm
        if mtm > peak_eq:
            peak_eq = mtm
        dd = (peak_eq - mtm) / peak_eq if peak_eq > 0.0 else 0.0
        if dd > max_dd:
            max_dd = dd

        if position != 0 and qty != 0.0 and (use_sl or use_tp or use_trail):
            hit, exit_raw, sl_px, peak_px = _stop_hit(
                position,
                high[i],
                low[i],
                use_sl,
                use_tp,
                use_trail,
                sl_px,
                tp_px,
                peak_px,
                trail_pct,
            )
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
            if not session_ok[i]:
                continue
            notional = cash * size_fraction * fill_fraction * leverage
            if notional <= 0.0 or cash <= 0.0:
                continue
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
            peak_px = entry
            if use_sl:
                sl_px = entry * (1.0 - sl_pct * 0.01) if target > 0 else entry * (
                    1.0 + sl_pct * 0.01
                )
            elif use_trail:
                sl_px = entry * (1.0 - trail_pct * 0.01) if target > 0 else entry * (
                    1.0 + trail_pct * 0.01
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
    session_ok: np.ndarray,
    fill_open: bool,
    long_short: bool,
    size_fraction: float,
    commission_bps: float,
    slip_bps: float,
    initial_cash: float,
    warmup: int,
    sl_pct: float,
    tp_pct: float,
    trail_pct: float,
    fill_fraction: float,
    leverage: float,
    funding_bps: float,
) -> float:
    """Scalar terminal return — same economics as :func:`run_core_full`."""
    _, ret, _, _, _, _, _, _, _, _, _, _, _ = run_core_full(
        open_,
        high,
        low,
        close,
        signal,
        session_ok,
        fill_open,
        long_short,
        size_fraction,
        commission_bps,
        slip_bps,
        initial_cash,
        warmup,
        sl_pct,
        tp_pct,
        trail_pct,
        fill_fraction,
        leverage,
        funding_bps,
    )
    return ret
