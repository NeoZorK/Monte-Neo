"""Parity: research Metal long/flat economics vs Numba golden."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.backtest import (
    ExecutionModel,
    frame_to_ohlc,
    get_metal_research_engine,
    metal_economics_eligible,
    run_bar_backtest_batch,
    sma_signal,
    synthetic_ohlcv,
)
from monte_neo.backtest.metal_economics import try_metal_batch_returns


def _fixture() -> tuple[dict[str, np.ndarray], np.ndarray, ExecutionModel]:
    ohlc = frame_to_ohlc(synthetic_ohlcv(800, seed=19))
    model = ExecutionModel(
        commission_bps=5.0,
        slippage_bps=5.0,
        size_fraction=0.5,
        warmup_bars=40,
        fill_fraction=0.8,
        leverage=1.5,
        side_mode="long_flat",
    )
    sigs = np.stack(
        [
            sma_signal(ohlc["close"], 5, 30),
            sma_signal(ohlc["close"], 8, 40),
            sma_signal(ohlc["close"], 10, 50),
        ]
    )
    return ohlc, sigs, model


def test_metal_eligible_blocks_advanced_knobs() -> None:
    assert metal_economics_eligible(ExecutionModel()) is True
    assert metal_economics_eligible(ExecutionModel(sl_pct=0.01)) is False
    assert metal_economics_eligible(ExecutionModel(funding_bps_per_bar=0.1)) is False
    mask = np.ones(10, dtype=np.bool_)
    mask[3] = False
    assert metal_economics_eligible(ExecutionModel(), mask) is False


def test_batch_cpu_device_forces_numba() -> None:
    ohlc, sigs, model = _fixture()
    out = run_bar_backtest_batch(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        sigs,
        model=model,
        device="cpu_numba",
    )
    assert out["device"] == "cpu_numba"
    assert out["ok"] is True


@pytest.mark.skipif(get_metal_research_engine() is None, reason="Metal research unavailable")
def test_metal_research_parity_vs_numba() -> None:
    ohlc, sigs, model = _fixture()
    cpu = run_bar_backtest_batch(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        sigs,
        model=model,
        device="cpu_numba",
    )
    metal = try_metal_batch_returns(
        ohlc["open"], ohlc["close"], sigs, model, device="metal"
    )
    assert metal is not None
    assert np.allclose(cpu["total_returns"], metal["returns"], rtol=1e-4, atol=1e-5)


@pytest.mark.skipif(get_metal_research_engine() is None, reason="Metal research unavailable")
def test_batch_auto_uses_metal_when_eligible() -> None:
    ohlc, sigs, model = _fixture()
    out = run_bar_backtest_batch(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        sigs,
        model=model,
        device="auto",
    )
    assert out["device"] == "metal"
