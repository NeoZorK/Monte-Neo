"""Signal factory parity and sweep wiring."""

from __future__ import annotations

import numpy as np

from monte_neo.backtest import (
    ExecutionModel,
    build_sma_cross_grid,
    build_sma_cross_grid_numba_golden,
    frame_to_ohlc,
    run_sma_sweep,
    synthetic_ohlcv,
)
from monte_neo.backtest.strategy import sma_signal_long_flat


def test_grid_matches_single_signals() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(800, seed=7))
    pairs = [(5, 30), (8, 40), (10, 40)]
    grid = build_sma_cross_grid(ohlc["close"], pairs, device="cpu_numba")
    assert grid["device"] == "cpu_numba"
    assert grid["signals"].shape == (3, 800)
    for i, (f, s) in enumerate(pairs):
        ref = sma_signal_long_flat(ohlc["close"].astype(np.float64), f, s)
        assert np.array_equal(grid["signals"][i], ref)


def test_golden_helper_matches_factory() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(500, seed=3))
    pairs = [(6, 20), (10, 40)]
    a = build_sma_cross_grid(ohlc["close"], pairs, device="cpu_numba")["signals"]
    b = build_sma_cross_grid_numba_golden(ohlc["close"], pairs)
    assert np.array_equal(a, b)


def test_sweep_exposes_signal_and_economics_timers() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(2000, seed=11))
    model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=40)
    out = run_sma_sweep(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"],
        combos=16, model=model, device="cpu_numba",
    )
    assert out["ok"] is True
    assert "signal_elapsed_s" in out
    assert "economics_elapsed_s" in out
    assert out["elapsed_s"] >= out["signal_elapsed_s"]
    assert out["combos"] == 16
