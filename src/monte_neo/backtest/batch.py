"""Batch signal backtests sharing the same ExecutionModel economics."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from numba import njit, prange

from monte_neo.backtest.core_numba import run_terminal_return
from monte_neo.backtest.model import ExecutionModel


@njit(cache=True, parallel=True)
def _batch_terminal_returns(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signals: np.ndarray,
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
) -> np.ndarray:
    m = signals.shape[0]
    out = np.empty(m, dtype=np.float64)
    for j in prange(m):
        out[j] = run_terminal_return(
            open_,
            high,
            low,
            close,
            signals[j],
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
        )
    return out


def run_bar_backtest_batch(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signals: np.ndarray,
    model: ExecutionModel | None = None,
) -> dict[str, Any]:
    """Run N external signal rows through the same engine."""
    model = model or ExecutionModel()
    o = np.asarray(open_, dtype=np.float64)
    h = np.asarray(high, dtype=np.float64)
    l = np.asarray(low, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    sig = np.asarray(signals, dtype=np.int64)
    if sig.ndim != 2:
        raise ValueError("signals must be 2-D (n_combos, n_bars)")
    if sig.shape[1] != o.shape[0]:
        raise ValueError("signals second dim must match OHLC length")
    if o.ndim != 1 or o.size < model.warmup_bars + 2:
        raise ValueError("need 1-D series with enough bars for warmup + fill")

    fill_open = model.fill_policy == "next_bar_open"
    long_short = model.side_mode == "long_short"
    slip = float(model.effective_slip_bps)
    args = (
        fill_open,
        long_short,
        float(model.size_fraction),
        float(model.commission_bps),
        slip,
        float(model.initial_cash),
        int(model.warmup_bars),
        float(model.sl_pct),
        float(model.tp_pct),
        float(model.trail_pct),
        float(model.fill_fraction),
    )
    _ = _batch_terminal_returns(
        o[: min(256, o.size)],
        h[: min(256, o.size)],
        l[: min(256, o.size)],
        c[: min(256, o.size)],
        sig[:1, : min(256, o.size)],
        fill_open,
        long_short,
        float(model.size_fraction),
        float(model.commission_bps),
        slip,
        float(model.initial_cash),
        min(int(model.warmup_bars), 10),
        float(model.sl_pct),
        float(model.tp_pct),
        float(model.trail_pct),
        float(model.fill_fraction),
    )
    t0 = time.perf_counter()
    rets = _batch_terminal_returns(o, h, l, c, sig, *args)
    elapsed = time.perf_counter() - t0
    n = int(sig.shape[0])
    return {
        "ok": True,
        "engine": "monte_neo.backtest.batch",
        "device": "cpu_numba",
        "model": model.to_dict(),
        "work_checklist": model.work_checklist,
        "combos": n,
        "elapsed_s": elapsed,
        "combos_per_s": n / elapsed if elapsed > 0 else float("inf"),
        "total_returns": rets,
        "best_return": float(np.max(rets)) if n else 0.0,
    }
