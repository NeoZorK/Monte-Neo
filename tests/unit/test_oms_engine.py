"""Unit tests for monte_neo.oms paper bar path."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.oms import (
    OrderSide,
    OrderType,
    PaperBroker,
    SignalStrategy,
    run_oms_bar_backtest,
)
from monte_neo.oms.accel.device import resolve_device
from monte_neo.oms.accel.match_numba import batch_terminal_long_flat
from monte_neo.oms.matching import MatchConfig, cancel_order
from monte_neo.oms.types import Order, OrderStatus


def _ohlc(n: int = 40, px: float = 100.0) -> tuple[np.ndarray, ...]:
    open_ = np.full(n, px, dtype=np.float64)
    high = open_ + 1.0
    low = open_ - 1.0
    close = open_.copy()
    return open_, high, low, close


def test_resolve_device_cpu() -> None:
    assert resolve_device("cpu_numba") == "cpu_numba"


def test_signal_strategy_market_path_ok() -> None:
    open_, high, low, close = _ohlc(50)
    signal = np.zeros(50, dtype=np.int64)
    signal[10:40] = 1
    out = run_oms_bar_backtest(
        open_,
        high,
        low,
        close,
        SignalStrategy(signal, size_fraction=1.0),
        commission_bps=0.0,
        slippage_bps=0.0,
        warmup_bars=0,
        device="cpu_numba",
        initial_cash=10_000.0,
    )
    assert out["ok"] is True
    assert out["lane"] == "oms_paper_bar"
    assert out["work_checklist"]["order_lifecycle"] is True
    assert out["blotter"]["n_fills"] >= 1
    assert np.isfinite(out["total_return"])


def test_cancel_before_fill() -> None:
    order = Order(
        order_id=1,
        symbol="SYM",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        qty=1.0,
        limit_px=99.0,
    )
    assert cancel_order(order) is True
    assert order.status == OrderStatus.CANCELED
    assert cancel_order(order) is False


def test_fees_hurt_oms_path() -> None:
    open_, high, low, close = _ohlc(80)
    signal = np.ones(80, dtype=np.int64)
    z = run_oms_bar_backtest(
        open_,
        high,
        low,
        close,
        SignalStrategy(signal),
        commission_bps=0.0,
        slippage_bps=0.0,
        warmup_bars=0,
        device="cpu_numba",
    )
    f = run_oms_bar_backtest(
        open_,
        high,
        low,
        close,
        SignalStrategy(signal),
        commission_bps=10.0,
        slippage_bps=10.0,
        warmup_bars=0,
        device="cpu_numba",
    )
    assert f["total_return"] <= z["total_return"] + 1e-12


def test_numba_batch_matches_shape() -> None:
    open_, _, _, close = _ohlc(100)
    sig = np.zeros((4, 100), dtype=np.int64)
    sig[:, 20:60] = 1
    rets = batch_terminal_long_flat(
        open_, close, sig, 5.0, 5.0, 100_000.0, 1.0, 0
    )
    assert rets.shape == (4,)
    assert np.all(np.isfinite(rets))


def test_paper_broker_rejects_bad_match_config() -> None:
    with pytest.raises(ValueError):
        MatchConfig(fill_policy="bad")


def test_limit_order_can_fill_on_range() -> None:
    open_, high, low, close = _ohlc(30, px=100.0)
    low[15] = 95.0
    broker = PaperBroker(
        commission_bps=0.0,
        slippage_bps=0.0,
        fill_policy="same_bar_close",
        device="cpu_numba",
        initial_cash=10_000.0,
    )
    # Manual submit path via engine
    eng = broker.engine
    eng.submit(
        {
            "side": OrderSide.BUY,
            "order_type": OrderType.LIMIT,
            "qty": 10.0,
            "limit_px": 96.0,
            "tag": "limit_buy",
        },
        bar_index=10,
    )
    # Drive a few bars
    class Idle:
        def on_bar(self, i, **kwargs):
            return []

    out = eng.run(open_, high, low, close, Idle())
    assert out["blotter"]["n_fills"] >= 1
