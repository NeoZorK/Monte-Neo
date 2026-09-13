"""Integration tests for monte_neo.backtest (end-to-end model checklist)."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.backtest import (
    ExecutionModel,
    ReplayBarSource,
    frame_to_ohlc,
    run_bar_backtest,
    run_sma_sweep,
    sma_signal,
    synthetic_ohlcv,
)


@pytest.fixture
def ohlc() -> dict[str, np.ndarray]:
    return frame_to_ohlc(synthetic_ohlcv(n_bars=3_000, seed=11))


def test_long_short_and_next_bar_close(ohlc: dict[str, np.ndarray]) -> None:
    model = ExecutionModel(
        fill_policy="next_bar_close",
        side_mode="long_short",
        size_fraction=0.5,
        commission_bps=2.0,
        slippage_bps=2.0,
        warmup_bars=40,
    )
    # Map long_flat SMA into signed signal: +1 / -1
    base = sma_signal(ohlc["close"], 8, 32)
    sig = np.where(base > 0, 1, -1).astype(np.int64)
    out = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model
    )
    assert out["ok"] is True
    assert out["model"]["fill_policy"] == "next_bar_close"
    assert out["model"]["side_mode"] == "long_short"
    assert out["n_trades"] >= 0
    assert np.isfinite(out["total_return"])


def test_replay_bar_source_feeds_engine() -> None:
    src = ReplayBarSource.from_synthetic_ticks(n_ticks=5_000, seed=3)
    ohlc = src.to_ohlc(bars=200)
    model = ExecutionModel(warmup_bars=20, commission_bps=1.0, slippage_bps=1.0)
    sig = sma_signal(ohlc["close"], 5, 20)
    out = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model
    )
    assert out["ok"] is True
    assert out["work_checklist"]["fees"] is True


def test_sweep_checklist_matches_model(ohlc: dict[str, np.ndarray]) -> None:
    model = ExecutionModel(commission_bps=7.0, slippage_bps=3.0, warmup_bars=25)
    out = run_sma_sweep(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], combos=16, model=model
    )
    assert out["work_checklist"] == model.work_checklist
    assert out["model"]["commission_bps"] == 7.0
