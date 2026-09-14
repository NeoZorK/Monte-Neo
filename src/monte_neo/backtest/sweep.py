"""Parallel SMA-grid sweep as a convenience wrapper over batch signals."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.backtest.bar_engine import run_bar_backtest
from monte_neo.backtest.batch import run_bar_backtest_batch
from monte_neo.backtest.core_numba import run_terminal_return
from monte_neo.backtest.model import ExecutionModel
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
    signals = np.empty((len(pairs), c.shape[0]), dtype=np.int64)
    for i, (fast, slow) in enumerate(pairs):
        signals[i] = sma_signal_long_flat(c, int(fast), int(slow))
    batch = run_bar_backtest_batch(
        open_, high, low, close, signals, model=model, device=device
    )
    rets = batch["total_returns"]
    return {
        "ok": True,
        "engine": "monte_neo.backtest.sweep",
        "device": batch.get("device", "cpu_numba"),
        "model": model.to_dict(),
        "work_checklist": model.work_checklist(),
        "combos": len(pairs),
        "elapsed_s": batch["elapsed_s"],
        "combos_per_s": batch["combos_per_s"],
        "best_return": float(batch["best_return"]),
        "rows": [
            {
                "fast": int(pairs[i][0]),
                "slow": int(pairs[i][1]),
                "total_return": float(rets[i]),
            }
            for i in range(len(pairs))
        ],
        "note": "SMA sweep wraps run_bar_backtest_batch (shared ExecutionModel)",
    }


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
