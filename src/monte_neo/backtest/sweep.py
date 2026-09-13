"""Parallel SMA-grid sweep using the professional bar engine."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from numba import njit, prange

from monte_neo.backtest.bar_engine import run_bar_backtest
from monte_neo.backtest.model import ExecutionModel


@njit(cache=True)
def _sma_signal_long_flat(close: np.ndarray, fast: int, slow: int) -> np.ndarray:
    n = close.shape[0]
    out = np.zeros(n, dtype=np.int64)
    if fast <= 0 or slow <= fast or slow > n:
        return out
    fsum = 0.0
    ssum = 0.0
    for i in range(n):
        fsum += close[i]
        ssum += close[i]
        if i >= fast:
            fsum -= close[i - fast]
        if i >= slow:
            ssum -= close[i - slow]
        if i + 1 < slow:
            continue
        out[i] = 1 if (fsum / fast) > (ssum / slow) else 0
    return out


@njit(cache=True, parallel=True)
def _batch_terminal_returns(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    fast_arr: np.ndarray,
    slow_arr: np.ndarray,
    fill_open: bool,
    size_fraction: float,
    commission_bps: float,
    slippage_bps: float,
    initial_cash: float,
    warmup: int,
) -> np.ndarray:
    """Compact parallel sweep returning terminal return only (equity omitted)."""
    m = fast_arr.shape[0]
    out = np.empty(m, dtype=np.float64)
    n = close.shape[0]
    fee_rate = commission_bps * 1e-4
    slip_rate = slippage_bps * 1e-4
    for j in prange(m):
        fast = int(fast_arr[j])
        slow = int(slow_arr[j])
        cash = initial_cash
        qty = 0.0
        position = 0
        fsum = 0.0
        ssum = 0.0
        for i in range(n):
            fsum += close[i]
            ssum += close[i]
            if i >= fast:
                fsum -= close[i - fast]
            if i >= slow:
                ssum -= close[i - slow]
            sig = 0
            if i + 1 >= slow:
                sig = 1 if (fsum / fast) > (ssum / slow) else 0
            if i < warmup or i + 1 >= n:
                continue
            if sig == position:
                continue
            fill_px = open_[i + 1] if fill_open else close[i + 1]
            if position != 0 and qty != 0.0:
                exit_px = fill_px * (1.0 - float(position) * slip_rate)
                proceeds = qty * exit_px
                cash += proceeds - abs(proceeds) * fee_rate
                qty = 0.0
                position = 0
            if sig != 0:
                notional = cash * size_fraction
                entry_px = fill_px * (1.0 + slip_rate)
                if entry_px > 0.0:
                    qty = notional / entry_px
                    cash -= qty * entry_px + abs(qty * entry_px) * fee_rate
                    position = 1
        if position != 0 and qty != 0.0:
            exit_px = close[n - 1] * (1.0 - slip_rate)
            proceeds = qty * exit_px
            cash += proceeds - abs(proceeds) * fee_rate
        out[j] = cash / initial_cash - 1.0
    return out


def run_sma_sweep(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    *,
    combos: int = 256,
    model: ExecutionModel | None = None,
) -> dict[str, Any]:
    """Fee-aware SMA long/flat parameter sweep (same model as single backtest)."""
    model = model or ExecutionModel(side_mode="long_flat")
    if model.side_mode != "long_flat":
        raise ValueError("run_sma_sweep currently supports long_flat only")
    pairs = [(f, s) for f in range(5, 21) for s in range(30, 51) if f < s][:combos]
    fast_arr = np.array([p[0] for p in pairs], dtype=np.int64)
    slow_arr = np.array([p[1] for p in pairs], dtype=np.int64)
    o = np.asarray(open_, dtype=np.float64)
    h = np.asarray(high, dtype=np.float64)
    l = np.asarray(low, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    # Warmup JIT
    _ = _batch_terminal_returns(
        o[: min(512, len(c))],
        h[: min(512, len(c))],
        l[: min(512, len(c))],
        c[: min(512, len(c))],
        fast_arr[:1],
        slow_arr[:1],
        model.fill_policy == "next_bar_open",
        float(model.size_fraction),
        float(model.commission_bps),
        float(model.slippage_bps),
        float(model.initial_cash),
        int(model.warmup_bars),
    )
    t0 = time.perf_counter()
    rets = _batch_terminal_returns(
        o,
        h,
        l,
        c,
        fast_arr,
        slow_arr,
        model.fill_policy == "next_bar_open",
        float(model.size_fraction),
        float(model.commission_bps),
        float(model.slippage_bps),
        float(model.initial_cash),
        int(model.warmup_bars),
    )
    elapsed = time.perf_counter() - t0
    n = len(pairs)
    return {
        "ok": True,
        "engine": "monte_neo.backtest.sweep",
        "device": "cpu_numba",
        "model": model.to_dict(),
        "work_checklist": model.work_checklist,
        "combos": n,
        "elapsed_s": elapsed,
        "combos_per_s": n / elapsed if elapsed > 0 else float("inf"),
        "best_return": float(np.max(rets)) if n else 0.0,
        "rows": [
            {"fast": int(fast_arr[i]), "slow": int(slow_arr[i]), "total_return": float(rets[i])}
            for i in range(n)
        ],
    }


def sma_signal(close: np.ndarray, fast: int, slow: int) -> np.ndarray:
    """Public helper: long/flat SMA cross signal (int64)."""
    return _sma_signal_long_flat(np.asarray(close, dtype=np.float64), int(fast), int(slow))


def verify_sweep_matches_single(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    *,
    fast: int,
    slow: int,
    model: ExecutionModel | None = None,
) -> bool:
    """Sanity: sweep scalar equals single-engine return for one pair."""
    model = model or ExecutionModel(side_mode="long_flat")
    sig = sma_signal(close, fast, slow)
    single = run_bar_backtest(open_, high, low, close, sig, model=model)
    # single combo sweep
    o = np.asarray(open_, dtype=np.float64)
    h = np.asarray(high, dtype=np.float64)
    l = np.asarray(low, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    rets = _batch_terminal_returns(
        o,
        h,
        l,
        c,
        np.array([fast], dtype=np.int64),
        np.array([slow], dtype=np.int64),
        model.fill_policy == "next_bar_open",
        float(model.size_fraction),
        float(model.commission_bps),
        float(model.slippage_bps),
        float(model.initial_cash),
        int(model.warmup_bars),
    )
    return abs(float(rets[0]) - float(single["total_return"])) < 1e-9
