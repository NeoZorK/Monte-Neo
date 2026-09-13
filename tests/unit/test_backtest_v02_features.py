"""Unit tests for v0.2.0 session / funding / leverage / shared portfolio."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.backtest import (
    ExecutionModel,
    frame_to_ohlc,
    run_bar_backtest,
    run_portfolio_shared_cash,
    sma_signal,
    synthetic_ohlcv,
)


def _flat_ohlc(n: int = 40, px: float = 100.0) -> dict[str, np.ndarray]:
    open_ = np.full(n, px)
    return {
        "open": open_,
        "high": open_ + 1.0,
        "low": open_ - 1.0,
        "close": open_.copy(),
    }


def test_session_mask_blocks_new_entries() -> None:
    ohlc = _flat_ohlc(50)
    signal = np.zeros(50, dtype=np.int64)
    signal[5:40] = 1
    mask = np.ones(50, dtype=np.bool_)
    mask[:20] = False
    model = ExecutionModel(
        warmup_bars=0,
        commission_bps=0.0,
        slippage_bps=0.0,
        initial_cash=10_000.0,
    )
    blocked = run_bar_backtest(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        signal,
        model=model,
        session_mask=mask,
    )
    open_sess = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], signal, model=model
    )
    assert blocked["work_checklist"]["session_mask"] is True
    assert blocked["n_closed_trades"] <= open_sess["n_closed_trades"]
    if blocked["trades"]:
        assert blocked["trades"][0]["entry_idx"] >= 21


def test_funding_hurts_hold() -> None:
    ohlc = _flat_ohlc(80)
    signal = np.ones(80, dtype=np.int64)
    z = ExecutionModel(
        warmup_bars=0,
        commission_bps=0.0,
        slippage_bps=0.0,
        funding_bps_per_bar=0.0,
        initial_cash=10_000.0,
    )
    f = ExecutionModel(
        warmup_bars=0,
        commission_bps=0.0,
        slippage_bps=0.0,
        funding_bps_per_bar=5.0,
        initial_cash=10_000.0,
    )
    a = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], signal, model=z
    )
    b = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], signal, model=f
    )
    assert b["total_return"] < a["total_return"]
    assert b["work_checklist"]["funding"] is True


def test_leverage_increases_qty() -> None:
    ohlc = _flat_ohlc(40)
    signal = np.zeros(40, dtype=np.int64)
    signal[5:30] = 1
    base = ExecutionModel(
        warmup_bars=0,
        commission_bps=0.0,
        slippage_bps=0.0,
        leverage=1.0,
        initial_cash=10_000.0,
    )
    lev = ExecutionModel(
        warmup_bars=0,
        commission_bps=0.0,
        slippage_bps=0.0,
        leverage=2.0,
        initial_cash=10_000.0,
    )
    a = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], signal, model=base
    )
    b = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], signal, model=lev
    )
    assert abs(b["trades"][0]["qty"]) > abs(a["trades"][0]["qty"]) * 1.5
    assert b["work_checklist"]["leverage"] is True


def test_shared_cash_portfolio_ok() -> None:
    ohlc_a = frame_to_ohlc(synthetic_ohlcv(1_200, seed=1))
    ohlc_b = frame_to_ohlc(synthetic_ohlcv(1_200, seed=2))
    model = ExecutionModel(
        warmup_bars=30,
        commission_bps=5.0,
        slippage_bps=5.0,
        size_fraction=0.4,
        initial_cash=100_000.0,
    )
    books = {"AAA": ohlc_a, "BBB": ohlc_b}
    signals = {
        "AAA": sma_signal(ohlc_a["close"], 8, 32),
        "BBB": sma_signal(ohlc_b["close"], 10, 40),
    }
    out = run_portfolio_shared_cash(books, signals, model=model)
    assert out["ok"] is True
    assert out["work_checklist"]["shared_cash_portfolio"] is True
    assert out["equity"].shape[0] == 1_200
    assert np.isfinite(out["total_return"])


def test_leverage_rejects_below_one() -> None:
    with pytest.raises(ValueError):
        ExecutionModel(leverage=0.5)
