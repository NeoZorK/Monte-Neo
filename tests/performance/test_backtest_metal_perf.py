"""Perf smoke for research Metal bar economics batch."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.backtest import (
    ExecutionModel,
    frame_to_ohlc,
    get_metal_research_engine,
    run_bar_backtest_batch,
    run_sma_sweep,
    sma_signal,
    synthetic_ohlcv,
)


@pytest.mark.skipif(get_metal_research_engine() is None, reason="Metal research unavailable")
def test_metal_sma_sweep_perf_smoke() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(5_000, seed=3))
    model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=50)
    _ = run_sma_sweep(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        combos=16,
        model=model,
        device="metal",
    )
    out = run_sma_sweep(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        combos=64,
        model=model,
        device="metal",
    )
    assert out["device"] == "metal"
    assert out["combos_per_s"] > 0
    assert out["ok"] is True


@pytest.mark.skipif(get_metal_research_engine() is None, reason="Metal research unavailable")
def test_metal_batch_with_sl_tp_uses_metal() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(1_000, seed=4))
    model = ExecutionModel(sl_pct=0.02, tp_pct=0.03, warmup_bars=40)
    sigs = np.stack([sma_signal(ohlc["close"], 5, 30)])
    out = run_bar_backtest_batch(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        sigs,
        model=model,
        device="metal",
    )
    assert out["device"] == "metal"
    assert out["ok"] is True
