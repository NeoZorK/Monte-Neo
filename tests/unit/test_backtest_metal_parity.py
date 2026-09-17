"""Parity: research Metal economics vs Numba golden."""

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


def _fixture(model: ExecutionModel | None = None) -> tuple:
    ohlc = frame_to_ohlc(synthetic_ohlcv(800, seed=19))
    model = model or ExecutionModel(
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


def test_metal_eligible_next_bar_open_only() -> None:
    assert metal_economics_eligible(ExecutionModel()) is True
    assert metal_economics_eligible(ExecutionModel(sl_pct=0.01, funding_bps_per_bar=0.1)) is True
    assert metal_economics_eligible(ExecutionModel(side_mode="long_short")) is True
    assert metal_economics_eligible(ExecutionModel(fill_policy="next_bar_close")) is False


def test_batch_cpu_device_forces_numba() -> None:
    ohlc, sigs, model = _fixture()
    out = run_bar_backtest_batch(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sigs,
        model=model, device="cpu_numba",
    )
    assert out["device"] == "cpu_numba"


def _parity(model: ExecutionModel, *, session_mask=None) -> None:
    ohlc, sigs, model = _fixture(model)
    cpu = run_bar_backtest_batch(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sigs,
        model=model, session_mask=session_mask, device="cpu_numba",
    )
    metal = try_metal_batch_returns(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sigs, model,
        session_ok=session_mask if session_mask is not None else None,
        device="metal",
    )
    assert metal is not None
    assert np.allclose(cpu["total_returns"], metal["returns"], rtol=1e-4, atol=1e-5)


@pytest.mark.skipif(get_metal_research_engine() is None, reason="Metal research unavailable")
def test_metal_parity_base() -> None:
    _parity(ExecutionModel(warmup_bars=40, size_fraction=0.5, fill_fraction=0.8, leverage=1.5))


@pytest.mark.skipif(get_metal_research_engine() is None, reason="Metal research unavailable")
def test_metal_parity_sl_tp_trail() -> None:
    _parity(ExecutionModel(warmup_bars=40, size_fraction=0.5, sl_pct=1.5, tp_pct=2.5, trail_pct=1.0))


@pytest.mark.skipif(get_metal_research_engine() is None, reason="Metal research unavailable")
def test_metal_parity_funding() -> None:
    _parity(ExecutionModel(warmup_bars=40, size_fraction=0.5, funding_bps_per_bar=0.5))


@pytest.mark.skipif(get_metal_research_engine() is None, reason="Metal research unavailable")
def test_metal_parity_session_mask() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(800, seed=19))
    mask = np.ones(ohlc["close"].shape[0], dtype=np.bool_)
    mask[100:120] = False
    mask[400:430] = False
    _parity(ExecutionModel(warmup_bars=40, size_fraction=0.5), session_mask=mask)


@pytest.mark.skipif(get_metal_research_engine() is None, reason="Metal research unavailable")
def test_metal_parity_long_short() -> None:
    _parity(ExecutionModel(warmup_bars=40, size_fraction=0.5, side_mode="long_short", sl_pct=1.0, tp_pct=2.0))


@pytest.mark.skipif(get_metal_research_engine() is None, reason="Metal research unavailable")
def test_batch_auto_prefers_cpu_numba_wall_clock() -> None:
    """v0.17.5+: research auto declines Metal for wall clock on typical grids."""
    ohlc, sigs, model = _fixture(ExecutionModel(warmup_bars=40, funding_bps_per_bar=0.2, side_mode="long_short"))
    out = run_bar_backtest_batch(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sigs,
        model=model, device="auto",
    )
    assert out["device"] == "cpu_numba"
    assert out.get("fallback_reason") == "auto_prefer_cpu_numba"


@pytest.mark.skipif(get_metal_research_engine() is None, reason="Metal research unavailable")
def test_batch_explicit_metal_uses_metal() -> None:
    ohlc, sigs, model = _fixture(ExecutionModel(warmup_bars=40, funding_bps_per_bar=0.2, side_mode="long_short"))
    out = run_bar_backtest_batch(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sigs,
        model=model, device="metal",
    )
    assert out["device"] == "metal"
