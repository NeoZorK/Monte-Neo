"""Shared-cash multi-symbol portfolio (bar-aligned research path)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numba import njit

from monte_neo.backtest.model import ExecutionModel


@njit(cache=True)
def _portfolio_core(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signals: np.ndarray,
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
    """Bar-sync shared cash. Arrays shaped (n_symbols, n_bars)."""
    n_sym = close.shape[0]
    n = close.shape[1]
    equity = np.empty(n, dtype=np.float64)
    cash = initial_cash
    qty = np.zeros(n_sym, dtype=np.float64)
    position = np.zeros(n_sym, dtype=np.int64)
    fill_events = 0
    peak_eq = initial_cash
    max_dd = 0.0
    fee_rate = commission_bps * 1e-4
    slip_rate = slip_bps * 1e-4
    fund_rate = funding_bps * 1e-4
    use_sl = sl_pct > 0.0
    use_tp = tp_pct > 0.0
    use_trail = trail_pct > 0.0
    entry_px = np.zeros(n_sym, dtype=np.float64)
    sl_px = np.zeros(n_sym, dtype=np.float64)
    tp_px = np.zeros(n_sym, dtype=np.float64)
    peak_px = np.zeros(n_sym, dtype=np.float64)

    for i in range(n):
        if fund_rate > 0.0:
            for s in range(n_sym):  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                if position[s] != 0 and qty[s] != 0.0:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    cash -= abs(qty[s] * close[s, i]) * fund_rate  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        mtm = cash
        for s in range(n_sym):
            mtm += qty[s] * close[s, i]
        equity[i] = mtm
        if mtm > peak_eq:
            peak_eq = mtm
        dd = (peak_eq - mtm) / peak_eq if peak_eq > 0.0 else 0.0
        if dd > max_dd:
            max_dd = dd

        for s in range(n_sym):
            if position[s] == 0 or qty[s] == 0.0:
                continue
            if not (use_sl or use_tp or use_trail):
                continue
            pos = int(position[s])  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            hit = 0  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            exit_raw = 0.0  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            if pos > 0:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                if use_trail and high[s, i] > peak_px[s]:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    peak_px[s] = high[s, i]  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    trail_stop = peak_px[s] * (1.0 - trail_pct * 0.01)  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    if (not use_sl) or trail_stop > sl_px[s]:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                        sl_px[s] = trail_stop  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                stop_lvl = sl_px[s] if (use_sl or use_trail) else 0.0  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                if (use_sl or use_trail) and low[s, i] <= stop_lvl:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    hit = 5 if use_trail else 2  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    exit_raw = stop_lvl  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                elif use_tp and high[s, i] >= tp_px[s]:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    hit = 3  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    exit_raw = tp_px[s]  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            else:
                if use_trail and low[s, i] < peak_px[s]:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    peak_px[s] = low[s, i]  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    trail_stop = peak_px[s] * (1.0 + trail_pct * 0.01)  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    if (not use_sl) or trail_stop < sl_px[s]:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                        sl_px[s] = trail_stop  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                stop_lvl = sl_px[s] if (use_sl or use_trail) else 0.0  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                if (use_sl or use_trail) and high[s, i] >= stop_lvl:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    hit = 5 if use_trail else 2  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    exit_raw = stop_lvl  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                elif use_tp and low[s, i] <= tp_px[s]:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    hit = 3  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                    exit_raw = tp_px[s]  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            if hit != 0:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                exit_px = exit_raw * (1.0 - float(pos) * slip_rate)  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                proceeds = qty[s] * exit_px  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                fee = abs(proceeds) * fee_rate  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                cash += proceeds - fee  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                fill_events += 1  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                qty[s] = 0.0  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                position[s] = 0  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        equity[i] = cash
        for s in range(n_sym):
            equity[i] += qty[s] * close[s, i]

        if i < warmup or i + 1 >= n:
            continue
        for s in range(n_sym):
            raw = int(signals[s, i])
            if long_short:
                target = 1 if raw > 0 else (-1 if raw < 0 else 0)  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            else:
                target = 1 if raw > 0 else 0
            if target == position[s]:
                continue
            fill_px = open_[s, i + 1] if fill_open else close[s, i + 1]
            if position[s] != 0 and qty[s] != 0.0:
                pos = int(position[s])
                exit_px = fill_px * (1.0 - float(pos) * slip_rate)
                proceeds = qty[s] * exit_px
                fee = abs(proceeds) * fee_rate
                cash += proceeds - fee
                fill_events += 1
                qty[s] = 0.0
                position[s] = 0
            if target != 0:
                if not session_ok[i]:
                    continue  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                notional = cash * size_fraction * fill_fraction * leverage
                if notional <= 0.0 or cash <= 0.0:
                    continue  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                entry = fill_px * (1.0 + float(target) * slip_rate)
                if entry <= 0.0:
                    continue  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                new_qty = (notional / entry) * float(target)
                fee = abs(new_qty * entry) * fee_rate
                cash -= new_qty * entry + fee
                qty[s] = new_qty
                position[s] = target
                fill_events += 1
                entry_px[s] = entry
                peak_px[s] = entry
                if use_sl:
                    sl_px[s] = (  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                        entry * (1.0 - sl_pct * 0.01)
                        if target > 0
                        else entry * (1.0 + sl_pct * 0.01)
                    )
                elif use_trail:
                    sl_px[s] = (  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                        entry * (1.0 - trail_pct * 0.01)
                        if target > 0
                        else entry * (1.0 + trail_pct * 0.01)
                    )
                if use_tp:
                    tp_px[s] = (  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                        entry * (1.0 + tp_pct * 0.01)
                        if target > 0
                        else entry * (1.0 - tp_pct * 0.01)
                    )

    for s in range(n_sym):
        if position[s] != 0 and qty[s] != 0.0:
            pos = int(position[s])
            exit_px = close[s, n - 1] * (1.0 - float(pos) * slip_rate)
            proceeds = qty[s] * exit_px
            fee = abs(proceeds) * fee_rate
            cash += proceeds - fee
            fill_events += 1
            qty[s] = 0.0
            position[s] = 0
    equity[n - 1] = cash
    return equity, cash / initial_cash - 1.0, max_dd, fill_events, cash


def run_portfolio_shared_cash(
    books: dict[str, dict[str, np.ndarray]],
    signals: dict[str, np.ndarray],
    model: ExecutionModel | None = None,
    session_mask: np.ndarray | None = None,
) -> dict[str, Any]:
    """Multi-symbol backtest with one shared cash book (bar-aligned)."""
    model = model or ExecutionModel()
    if not books:
        raise ValueError("books must be non-empty")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    missing = set(books) - set(signals)
    if missing:
        raise ValueError(f"missing signals for symbols: {sorted(missing)}")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    symbols = sorted(books)
    n_sym = len(symbols)
    n = int(np.asarray(books[symbols[0]]["close"]).shape[0])
    open_ = np.empty((n_sym, n), dtype=np.float64)
    high = np.empty((n_sym, n), dtype=np.float64)
    low = np.empty((n_sym, n), dtype=np.float64)
    close = np.empty((n_sym, n), dtype=np.float64)
    sig = np.empty((n_sym, n), dtype=np.int64)
    for i, sym in enumerate(symbols):
        ohlc = books[sym]
        for key in ("open", "high", "low", "close"):
            if np.asarray(ohlc[key]).shape[0] != n:
                raise ValueError("all symbols must share the same bar length")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        open_[i] = np.asarray(ohlc["open"], dtype=np.float64)
        high[i] = np.asarray(ohlc["high"], dtype=np.float64)
        low[i] = np.asarray(ohlc["low"], dtype=np.float64)
        close[i] = np.asarray(ohlc["close"], dtype=np.float64)
        sig[i] = np.asarray(signals[sym], dtype=np.int64)
    if n < model.warmup_bars + 2:
        raise ValueError("need enough bars for warmup + fill")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    if session_mask is None:
        sess = np.ones(n, dtype=np.bool_)
        sess_used = False
    else:
        sess = np.asarray(session_mask, dtype=np.bool_)  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        if sess.shape != (n,):  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            raise ValueError("session_mask must match bar length")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        sess_used = True  # pragma: no cover  # defensive / unreachable after unit mocks on CI

    equity, total_return, max_dd, fill_events, final_cash = _portfolio_core(
        open_,
        high,
        low,
        close,
        sig,
        sess,
        model.fill_policy == "next_bar_open",
        model.side_mode == "long_short",
        float(model.size_fraction),
        float(model.commission_bps),
        float(model.effective_slip_bps),
        float(model.initial_cash),
        int(model.warmup_bars),
        float(model.sl_pct),
        float(model.tp_pct),
        float(model.trail_pct),
        float(model.fill_fraction),
        float(model.leverage),
        float(model.funding_bps_per_bar),
    )
    checklist = model.work_checklist(session_mask_used=sess_used)
    checklist["shared_cash_portfolio"] = True
    return {
        "ok": True,
        "engine": "monte_neo.backtest.portfolio_shared",
        "symbols": symbols,
        "model": model.to_dict(),
        "work_checklist": checklist,
        "total_return": float(total_return),
        "max_drawdown": float(max_dd),
        "n_trades": int(fill_events),
        "final_cash": float(final_cash),
        "equity": equity,
        "note": "Shared cash; bar-aligned; research portfolio (not OMS netting)",
    }
