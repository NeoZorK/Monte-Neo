"""Unit tests for monte_neo.backtest professional engine."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.backtest import (
    ExecutionModel,
    assert_fee_hurts_return,
    frame_to_ohlc,
    ReplayBarSource,
    midprice_ticks_to_ohlc,
    run_bar_backtest,
    run_sma_sweep,
    sma_signal,
    summarize_equity,
    synthetic_ohlcv,
    try_import_replay_inprocess,
    verify_sweep_matches_single,
)


@pytest.fixture
def ohlc() -> dict[str, np.ndarray]:
    df = synthetic_ohlcv(n_bars=2_000, seed=7)
    return frame_to_ohlc(df)


def test_execution_model_rejects_bad_size() -> None:
    with pytest.raises(ValueError):
        ExecutionModel(size_fraction=0.0)


def test_next_bar_no_lookahead_and_trades(ohlc: dict[str, np.ndarray]) -> None:
    model = ExecutionModel(
        fill_policy="next_bar_open",
        side_mode="long_flat",
        size_fraction=0.25,
        commission_bps=5.0,
        slippage_bps=5.0,
        warmup_bars=30,
    )
    sig = sma_signal(ohlc["close"], 10, 40)
    out = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model
    )
    assert out["ok"] is True
    assert out["work_checklist"]["next_bar_fill"] is True
    assert out["work_checklist"]["cash_position_equity"] is True
    assert out["n_trades"] >= 0
    assert out["equity"].shape[0] == ohlc["close"].shape[0]
    summ = summarize_equity(out["equity"], initial_cash=model.initial_cash)
    assert abs(summ["total_return"] - out["total_return"]) < 1e-9


def test_fees_do_not_improve_return(ohlc: dict[str, np.ndarray]) -> None:
    sig = sma_signal(ohlc["close"], 8, 35)
    zero = ExecutionModel(commission_bps=0.0, slippage_bps=0.0, warmup_bars=20)
    fee = ExecutionModel(commission_bps=10.0, slippage_bps=10.0, warmup_bars=20)
    a = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=zero
    )
    b = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=fee
    )
    assert_fee_hurts_return(a, b)


def test_sweep_throughput_and_consistency(ohlc: dict[str, np.ndarray]) -> None:
    model = ExecutionModel(
        commission_bps=5.0, slippage_bps=5.0, size_fraction=0.25, warmup_bars=40
    )
    out = run_sma_sweep(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        combos=32,
        model=model,
    )
    assert out["ok"] is True
    assert out["combos"] == 32
    assert out["combos_per_s"] > 0
    assert verify_sweep_matches_single(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        fast=5,
        slow=30,
        model=model,
    )


def test_midprice_feeder_shapes() -> None:
    rng = np.random.default_rng(0)
    bid = 100 + rng.normal(0, 0.1, size=1_000)
    ask = bid + 0.02
    ohlc = midprice_ticks_to_ohlc(bid, ask, bars=50)
    assert ohlc["close"].shape == (50,)
    assert np.all(ohlc["high"] >= ohlc["low"])
    src = ReplayBarSource(bids=bid, asks=ask)
    assert src.to_ohlc(bars=50)["close"].shape == (50,)


def test_replay_import_is_safe() -> None:
    info = try_import_replay_inprocess()
    assert "ok" in info


def test_deterministic_synthetic_seed() -> None:
    a = frame_to_ohlc(synthetic_ohlcv(200, seed=1))
    b = frame_to_ohlc(synthetic_ohlcv(200, seed=1))
    assert np.allclose(a["close"], b["close"])
