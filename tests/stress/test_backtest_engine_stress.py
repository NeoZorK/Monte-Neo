"""Stress tests for monte_neo.backtest (larger grids / longer series)."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.backtest import (
    ExecutionModel,
    frame_to_ohlc,
    run_bar_backtest,
    run_sma_sweep,
    sma_signal,
    synthetic_ohlcv,
)


@pytest.mark.stress
def test_long_series_single_backtest() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(n_bars=50_000, seed=99))
    model = ExecutionModel(warmup_bars=60, size_fraction=0.25)
    sig = sma_signal(ohlc["close"], 12, 48)
    out = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model
    )
    assert out["ok"] is True
    assert out["equity"].shape[0] == 50_000
    assert np.isfinite(out["final_cash"])


@pytest.mark.stress
def test_sweep_256_combos_stable() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(n_bars=10_000, seed=5))
    model = ExecutionModel(warmup_bars=50, commission_bps=5.0, slippage_bps=5.0)
    out = run_sma_sweep(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], combos=256, model=model
    )
    assert out["ok"] is True
    assert out["combos"] == 256
    assert all(np.isfinite(row["total_return"]) for row in out["rows"])
