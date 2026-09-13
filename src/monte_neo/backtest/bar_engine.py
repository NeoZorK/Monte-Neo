"""Numba bar engine: next-bar fills, fees, slippage, cash/position/equity."""

from __future__ import annotations

from typing import Any

import numpy as np
from numba import njit

from monte_neo.backtest.model import ExecutionModel, FillPolicy, SideMode


@njit(cache=True)
def _run_core(
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
) -> tuple[np.ndarray, float, float, int, float]:
    n = close.shape[0]
    equity = np.empty(n, dtype=np.float64)
    cash = initial_cash
    qty = 0.0
    position = 0  # -1, 0, +1
    trades = 0
    peak = initial_cash
    max_dd = 0.0
    fee_rate = commission_bps * 1e-4
    slip_rate = slippage_bps * 1e-4

    for i in range(n):
        # Mark-to-market equity on close
        mtm = cash + qty * close[i]
        equity[i] = mtm
        if mtm > peak:
            peak = mtm
        dd = (peak - mtm) / peak if peak > 0.0 else 0.0
        if dd > max_dd:
            max_dd = dd

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

        # Close existing
        if position != 0 and qty != 0.0:
            exit_px = fill_px * (1.0 - float(position) * slip_rate)
            proceeds = qty * exit_px
            fee = abs(proceeds) * fee_rate
            cash += proceeds - fee
            qty = 0.0
            trades += 1
            position = 0

        # Open new
        if target != 0:
            mtm2 = cash
            notional = mtm2 * size_fraction
            entry_px = fill_px * (1.0 + float(target) * slip_rate)
            if entry_px <= 0.0:
                continue
            new_qty = (notional / entry_px) * float(target)
            fee = abs(new_qty * entry_px) * fee_rate
            cash -= new_qty * entry_px + fee
            qty = new_qty
            position = target
            trades += 1

    # Flatten at last close
    if position != 0 and qty != 0.0:
        exit_px = close[n - 1] * (1.0 - float(position) * slip_rate)
        proceeds = qty * exit_px
        fee = abs(proceeds) * fee_rate
        cash += proceeds - fee
        qty = 0.0
        trades += 1
        equity[n - 1] = cash

    total_return = cash / initial_cash - 1.0
    return equity, total_return, max_dd, trades, cash


def run_bar_backtest(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signal: np.ndarray,
    model: ExecutionModel | None = None,
) -> dict[str, Any]:
    """Run one bar backtest under a frozen :class:`ExecutionModel`."""
    model = model or ExecutionModel()
    o = np.asarray(open_, dtype=np.float64)
    h = np.asarray(high, dtype=np.float64)
    l = np.asarray(low, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    s = np.asarray(signal, dtype=np.int64)
    if not (o.shape == h.shape == l.shape == c.shape == s.shape):
        raise ValueError("OHLC and signal must share the same shape")
    if o.ndim != 1 or o.size < model.warmup_bars + 2:
        raise ValueError("need 1-D series with enough bars for warmup + fill")

    fill_open = model.fill_policy == "next_bar_open"
    long_short = model.side_mode == "long_short"
    equity, total_return, max_dd, trades, final_cash = _run_core(
        o,
        h,
        l,
        c,
        s,
        fill_open,
        long_short,
        float(model.size_fraction),
        float(model.commission_bps),
        float(model.slippage_bps),
        float(model.initial_cash),
        int(model.warmup_bars),
    )
    return {
        "ok": True,
        "engine": "monte_neo.backtest",
        "model": model.to_dict(),
        "work_checklist": model.work_checklist,
        "total_return": float(total_return),
        "max_drawdown": float(max_dd),
        "n_trades": int(trades),
        "final_cash": float(final_cash),
        "equity": equity,
    }


# typing helpers for static checkers (FillPolicy/SideMode imported for docs)
_ = (FillPolicy, SideMode)
