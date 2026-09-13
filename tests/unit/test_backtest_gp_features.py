"""Unit tests for strategy specs, trail, impact, and partial fills."""

from __future__ import annotations

import numpy as np

from monte_neo.backtest import (
    ExecutionModel,
    StrategySpec,
    build_signal,
    frame_to_ohlc,
    run_bar_backtest,
    run_strategy_backtest,
    sma_signal,
    synthetic_ohlcv,
)


def test_strategy_spec_sma_matches_helper() -> None:
    close = frame_to_ohlc(synthetic_ohlcv(800, seed=3))["close"]
    a = build_signal(close, StrategySpec(kind="sma_cross", fast=8, slow=32))
    b = sma_signal(close, 8, 32)
    assert np.array_equal(a, b)


def test_run_strategy_backtest_ok() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(1_500, seed=4))
    model = ExecutionModel(warmup_bars=40, commission_bps=5.0, slippage_bps=5.0)
    out = run_strategy_backtest(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        StrategySpec(kind="ema_cross", fast=10, slow=40),
        model=model,
    )
    assert out["ok"] is True
    assert out["strategy"]["kind"] == "ema_cross"
    assert out["work_checklist"]["strategy_expressions"] is True


def test_partial_fill_reduces_exposure() -> None:
    n = 40
    open_ = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    signal = np.zeros(n, dtype=np.int64)
    signal[5:30] = 1
    full = ExecutionModel(
        warmup_bars=0,
        commission_bps=0.0,
        slippage_bps=0.0,
        fill_fraction=1.0,
        initial_cash=10_000.0,
    )
    half = ExecutionModel(
        warmup_bars=0,
        commission_bps=0.0,
        slippage_bps=0.0,
        fill_fraction=0.5,
        initial_cash=10_000.0,
    )
    a = run_bar_backtest(open_, high, low, close, signal, model=full)
    b = run_bar_backtest(open_, high, low, close, signal, model=half)
    assert a["n_closed_trades"] >= 1 and b["n_closed_trades"] >= 1
    assert abs(a["trades"][0]["qty"]) > abs(b["trades"][0]["qty"])


def test_impact_bps_hurts_vs_zero_impact() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(2_000, seed=9))
    sig = sma_signal(ohlc["close"], 10, 40)
    z = ExecutionModel(warmup_bars=30, commission_bps=0.0, slippage_bps=0.0, impact_bps=0.0)
    i = ExecutionModel(warmup_bars=30, commission_bps=0.0, slippage_bps=0.0, impact_bps=20.0)
    a = run_bar_backtest(ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=z)
    b = run_bar_backtest(ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=i)
    assert b["total_return"] <= a["total_return"] + 1e-12
    assert b["work_checklist"]["impact"] is True


def test_trail_can_exit() -> None:
    n = 40
    open_ = np.linspace(100.0, 120.0, n)
    high = open_ + 1.0
    low = open_ - 1.0
    close = open_.copy()
    # Sharp drop after run-up
    open_[25:] = 110.0
    high[25:] = 111.0
    low[25] = 100.0
    close[25:] = 101.0
    signal = np.ones(n, dtype=np.int64)
    model = ExecutionModel(
        warmup_bars=0,
        commission_bps=0.0,
        slippage_bps=0.0,
        trail_pct=2.0,
        sl_pct=0.0,
        tp_pct=0.0,
        initial_cash=10_000.0,
    )
    out = run_bar_backtest(open_, high, low, close, signal, model=model)
    assert out["work_checklist"]["trail"] is True
    reasons = {t["reason"] for t in out["trades"]}
    assert "trail" in reasons or out["n_closed_trades"] >= 1
