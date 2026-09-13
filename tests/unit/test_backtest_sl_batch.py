"""Unit tests for SL/TP, journal, batch, and multi-symbol lite."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.backtest import (
    ExecutionModel,
    frame_to_ohlc,
    run_bar_backtest,
    run_bar_backtest_batch,
    run_multi_symbol_lite,
    sma_signal,
    synthetic_ohlcv,
)


@pytest.fixture
def ohlc() -> dict[str, np.ndarray]:
    return frame_to_ohlc(synthetic_ohlcv(n_bars=3_000, seed=21))


def test_sl_triggers_and_journals_reason() -> None:
    n = 30
    open_ = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    # After entry at bar 6 open=100, bar 7 dumps through SL
    open_[6] = 100.0
    high[7] = 100.5
    low[7] = 90.0
    close[7] = 91.0
    signal = np.zeros(n, dtype=np.int64)
    # Stay long so SL can fire on bar 7 before any signal exit.
    signal[5:15] = 1
    model = ExecutionModel(
        fill_policy="next_bar_open",
        commission_bps=0.0,
        slippage_bps=0.0,
        warmup_bars=0,
        initial_cash=10_000.0,
        sl_pct=5.0,
        tp_pct=0.0,
    )
    out = run_bar_backtest(open_, high, low, close, signal, model=model)
    assert out["work_checklist"]["sl_tp"] is True
    assert out["n_closed_trades"] >= 1
    reasons = {t["reason"] for t in out["trades"]}
    assert "sl" in reasons
    assert out["metrics"]["n_closed_trades"] >= 1.0


def test_batch_matches_single(ohlc: dict[str, np.ndarray]) -> None:
    model = ExecutionModel(
        commission_bps=5.0,
        slippage_bps=5.0,
        warmup_bars=40,
        size_fraction=0.25,
        sl_pct=1.0,
        tp_pct=2.0,
    )
    s0 = sma_signal(ohlc["close"], 8, 32)
    s1 = sma_signal(ohlc["close"], 10, 40)
    signals = np.vstack([s0, s1])
    batch = run_bar_backtest_batch(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], signals, model=model
    )
    a = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], s0, model=model
    )
    b = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], s1, model=model
    )
    assert abs(float(batch["total_returns"][0]) - a["total_return"]) < 1e-9
    assert abs(float(batch["total_returns"][1]) - b["total_return"]) < 1e-9


def test_multi_symbol_lite_two_books(ohlc: dict[str, np.ndarray]) -> None:
    model = ExecutionModel(warmup_bars=30, commission_bps=2.0, slippage_bps=2.0)
    sig = sma_signal(ohlc["close"], 9, 36)
    out = run_multi_symbol_lite(
        {"AAA": ohlc, "BBB": ohlc},
        {"AAA": sig, "BBB": sig},
        model=model,
    )
    assert out["n_symbols"] == 2
    assert out["ok"] is True
    assert "AAA" in out["per_symbol"]
    assert np.isfinite(out["portfolio_return"])


def test_metrics_keys_present(ohlc: dict[str, np.ndarray]) -> None:
    model = ExecutionModel(warmup_bars=25)
    sig = sma_signal(ohlc["close"], 7, 28)
    out = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model
    )
    for key in ("sharpe", "profit_factor", "win_rate", "max_drawdown", "total_return"):
        assert key in out["metrics"]
