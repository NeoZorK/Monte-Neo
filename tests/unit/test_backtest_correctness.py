"""Correctness invariants for the professional bar engine."""

from __future__ import annotations

import numpy as np

from monte_neo.backtest import (
    ExecutionModel,
    assert_fee_hurts_return,
    frame_to_ohlc,
    run_bar_backtest,
    run_bar_backtest_batch,
    sma_signal,
    synthetic_ohlcv,
)


def test_sl_preferred_on_dual_hit_same_bar() -> None:
    """When low hits SL and high hits TP same bar, SL fills (OCO honesty)."""
    n = 30
    open_ = np.full(n, 100.0)
    high = np.full(n, 100.0)
    low = np.full(n, 100.0)
    close = np.full(n, 100.0)
    # Entry on bar 6 open at 100 after signal at 5
    high[10] = 110.0  # TP 2% would be 102
    low[10] = 90.0  # SL 1% would be 99
    close[10] = 100.0
    signal = np.zeros(n, dtype=np.int64)
    signal[5:] = 1
    model = ExecutionModel(
        warmup_bars=0,
        commission_bps=0.0,
        slippage_bps=0.0,
        sl_pct=1.0,
        tp_pct=2.0,
        oco_bracket=True,
        initial_cash=10_000.0,
    )
    out = run_bar_backtest(open_, high, low, close, signal, model=model)
    assert out["n_closed_trades"] >= 1
    first = out["trades"][0]
    assert first["reason"] in {"sl", "trail"}
    assert first["exit_px"] <= 99.0 + 1e-9


def test_batch_matches_single_with_funding_leverage() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(2_500, seed=21))
    sig = sma_signal(ohlc["close"], 12, 48)
    model = ExecutionModel(
        warmup_bars=40,
        commission_bps=4.0,
        slippage_bps=3.0,
        impact_bps=1.0,
        leverage=1.5,
        funding_bps_per_bar=0.2,
        sl_pct=1.0,
        tp_pct=2.0,
        trail_pct=0.5,
    )
    single = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model
    )
    batch = run_bar_backtest_batch(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        sig.reshape(1, -1),
        model=model,
    )
    assert abs(float(batch["total_returns"][0]) - single["total_return"]) < 1e-9


def test_fees_still_hurt_with_new_knobs() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(1_800, seed=5))
    sig = sma_signal(ohlc["close"], 9, 36)
    zero = ExecutionModel(
        warmup_bars=25,
        commission_bps=0.0,
        slippage_bps=0.0,
        leverage=1.0,
        funding_bps_per_bar=0.0,
    )
    fee = ExecutionModel(
        warmup_bars=25,
        commission_bps=8.0,
        slippage_bps=8.0,
        leverage=1.0,
        funding_bps_per_bar=0.0,
    )
    a = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=zero
    )
    b = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=fee
    )
    assert_fee_hurts_return(a, b)
