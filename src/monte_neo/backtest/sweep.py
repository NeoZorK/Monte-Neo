"""Parallel SMA-grid sweep as a convenience wrapper over batch signals."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.backtest.bar_engine import run_bar_backtest
from monte_neo.backtest.batch import run_bar_backtest_batch
from monte_neo.backtest.core_numba import run_terminal_return
from monte_neo.backtest.memory_plan import decide_research_accelerator
from monte_neo.backtest.model import ExecutionModel
from monte_neo.backtest.signal_factory import build_sma_cross_grid
from monte_neo.backtest.strategy import sma_signal_long_flat


def _sma_pairs(combos: int) -> list[tuple[int, int]]:
    return [(f, s) for f in range(5, 21) for s in range(30, 51) if f < s][:combos]


def run_sma_sweep(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    *,
    combos: int = 256,
    model: ExecutionModel | None = None,
    device: str = "auto",
) -> dict[str, Any]:
    """Fee-aware SMA long/flat sweep via :func:`run_bar_backtest_batch`.

    Convenience wrapper only — economics come from the shared ExecutionModel
    path (not a specialized D001 fused kernel). Metal when eligible + available.
    """
    model = model or ExecutionModel(side_mode="long_flat")
    if model.side_mode != "long_flat":
        raise ValueError("run_sma_sweep currently supports long_flat only")
    pairs = _sma_pairs(combos)
    c = np.asarray(close, dtype=np.float64)
    # Signal device: MLX only when explicitly requested and size gate allows.
    accel = decide_research_accelerator(
        n_bars=int(c.shape[0]), n_combos=len(pairs), device=device
    )
    if device == "mlx" and accel.get("use_mlx"):
        sig_device = "mlx"
    elif device in ("auto", "metal", "mlx"):
        sig_device = "cpu_numba" if accel.get("fallback_reason") else "auto"
    else:
        sig_device = "cpu_numba"
    sig = build_sma_cross_grid(c, pairs, device=sig_device)
    signals = sig["signals"]
    batch = run_bar_backtest_batch(
        open_, high, low, close, signals, model=model, device=device
    )
    rets = batch["total_returns"]
    total_elapsed = float(sig["elapsed_s"]) + float(batch["elapsed_s"])
    out = {
        "ok": True,
        "engine": "monte_neo.backtest.sweep",
        "device": batch.get("device", "cpu_numba"),
        "signal_device": sig.get("device"),
        "signal_elapsed_s": sig.get("elapsed_s"),
        "economics_elapsed_s": batch.get("elapsed_s"),
        "model": model.to_dict(),
        "work_checklist": model.work_checklist(),
        "combos": len(pairs),
        "elapsed_s": total_elapsed,
        "combos_per_s": (len(pairs) / total_elapsed) if total_elapsed > 0 else 0.0,
        "best_return": float(batch["best_return"]),
        "rows": [
            {
                "fast": int(pairs[i][0]),
                "slow": int(pairs[i][1]),
                "total_return": float(rets[i]),
            }
            for i in range(len(pairs))
        ],
        "note": "SMA sweep: signal_factory + run_bar_backtest_batch (shared ExecutionModel)",
    }
    reason = batch.get("fallback_reason") or (
        accel.get("fallback_reason") if batch.get("device") == "cpu_numba" and device in ("auto", "metal", "mlx") else None
    )
    if reason and out["device"] == "cpu_numba" and device != "cpu_numba":
        out["fallback_reason"] = reason
    return out


def sma_signal(close: np.ndarray, fast: int, slow: int) -> np.ndarray:
    """Public helper: long/flat SMA cross signal (int64)."""
    return sma_signal_long_flat(np.asarray(close, dtype=np.float64), int(fast), int(slow))


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
    n = int(np.asarray(close).shape[0])
    sess = np.ones(n, dtype=np.bool_)
    term = run_terminal_return(
        np.asarray(open_, dtype=np.float64),
        np.asarray(high, dtype=np.float64),
        np.asarray(low, dtype=np.float64),
        np.asarray(close, dtype=np.float64),
        np.asarray(sig, dtype=np.int64),
        sess,
        model.fill_policy == "next_bar_open",
        False,
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
    return abs(float(term) - float(single["total_return"])) < 1e-9
