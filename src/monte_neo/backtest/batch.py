"""Batch signal backtests sharing the same ExecutionModel economics."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from numba import njit, prange

from monte_neo.backtest.core_numba import run_terminal_return
from monte_neo.backtest.memory_plan import decide_research_accelerator
from monte_neo.backtest.metal_economics import (
    metal_economics_eligible,
    try_metal_batch_returns,
)
from monte_neo.backtest.model import ExecutionModel


@njit(cache=True, parallel=True)
def _batch_terminal_returns(  # pragma: no cover  # njit body; covered via NUMBA_DISABLE_JIT subprocess
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
    return out


def run_bar_backtest_batch(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signals: np.ndarray,
    model: ExecutionModel | None = None,
    session_mask: np.ndarray | None = None,
    *,
    device: str = "auto",
) -> dict[str, Any]:
    """Run N external signal rows through the same engine.

    Metal is used for next-bar-open research economics (SL/TP/trail/funding/
    session/long_short) when ``device`` resolves to metal; else Numba golden.
    """
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
    if session_mask is None:
        sess = np.ones(o.size, dtype=np.bool_)
        sess_used = False
    else:
        sess = np.asarray(session_mask, dtype=np.bool_)
        if sess.shape != (o.size,):
            raise ValueError("session_mask must match bar length")
        sess_used = True

    fallback_reason: str | None = None
    if metal_economics_eligible(model, sess if sess_used else None):
        decision = decide_research_accelerator(
            n_bars=int(o.shape[0]), n_combos=int(sig.shape[0]), device=device
        )
        if decision["use_metal"]:
            t0 = time.perf_counter()
            metal_out = try_metal_batch_returns(
                o,
                h,
                l,
                c,
                sig,
                model,
                session_ok=sess,
                device=device,
                tile_combos=decision.get("metal_tile_combos"),
            )
            elapsed = time.perf_counter() - t0
            if metal_out is not None and metal_out.get("ok") and metal_out.get("returns") is not None:
                rets = metal_out["returns"]
                n = int(sig.shape[0])
                out = {
                    "ok": True,
                    "engine": "monte_neo.backtest.batch",
                    "device": "metal",
                    "model": model.to_dict(),
                    "work_checklist": model.work_checklist(session_mask_used=sess_used),
                    "combos": n,
                    "elapsed_s": elapsed,
                    "combos_per_s": n / elapsed if elapsed > 0 else float("inf"),
                    "total_returns": rets,
                    "best_return": float(np.max(rets)) if n else 0.0,
                }
                if metal_out.get("tiles", 1) > 1:
                    out["metal_tiles"] = int(metal_out["tiles"])
                    out["metal_tile_combos"] = int(metal_out.get("tile_combos") or 0)
                return out
            fallback_reason = (
                (metal_out or {}).get("fallback_reason")
                if isinstance(metal_out, dict)
                else None
            ) or "metal_unavailable_or_failed"
        else:
            fallback_reason = decision.get("fallback_reason")

    fill_open = model.fill_policy == "next_bar_open"
    long_short = model.side_mode == "long_short"
    slip = float(model.effective_slip_bps)
    args = (
        sess,
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
        float(model.leverage),
        float(model.funding_bps_per_bar),
    )
    warm_n = min(256, o.size)
    _ = _batch_terminal_returns(
        o[:warm_n],
        h[:warm_n],
        l[:warm_n],
        c[:warm_n],
        sig[:1, :warm_n],
        sess[:warm_n],
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
        float(model.leverage),
        float(model.funding_bps_per_bar),
    )
    t0 = time.perf_counter()
    rets = _batch_terminal_returns(o, h, l, c, sig, *args)
    elapsed = time.perf_counter() - t0
    n = int(sig.shape[0])
    out = {
        "ok": True,
        "engine": "monte_neo.backtest.batch",
        "device": "cpu_numba",
        "model": model.to_dict(),
        "work_checklist": model.work_checklist(session_mask_used=sess_used),
        "combos": n,
        "elapsed_s": elapsed,
        "combos_per_s": n / elapsed if elapsed > 0 else float("inf"),
        "total_returns": rets,
        "best_return": float(np.max(rets)) if n else 0.0,
    }
    if fallback_reason:
        out["fallback_reason"] = fallback_reason
    return out
