"""Gap-close coverage: clock, TIF/GTC, OCO, partials, replay, accel hygiene."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.oms import (
    BarClock,
    OmsEngine,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
    run_ohlc_replay,
    submit_bracket,
)
from monte_neo.oms.accel import BufferPool, list_shaders, load_shader_source
from monte_neo.oms.matching import MatchConfig
from monte_neo.oms.strategy import Strategy


class Idle(Strategy):
    def on_bar(self, i, **kw):
        return []


def _ohlc(n=20, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.2, size=n))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) + 0.5
    low = np.minimum(open_, close) - 0.5
    return open_, high, low, close


def test_bar_clock_monotonic():
    c = BarClock()
    assert c.advance(bars=1) == 1
    c.at(5, ts_ns=10)
    with pytest.raises(ValueError):
        c.advance(ts_ns=1)


def test_gtc_limit_rests_until_hit():
    eng = OmsEngine(match=MatchConfig(commission_bps=0, slippage_bps=0))
    o, h, l, c = _ohlc(30)
    # force a low that hits buy limit
    l[10] = 50.0
    eng.submit(
        {
            "side": OrderSide.BUY,
            "order_type": OrderType.LIMIT,
            "qty": 1.0,
            "limit_px": 60.0,
            "tif": TimeInForce.GTC,
        },
        bar_index=0,
    )
    eng.run(o, h, l, c, Idle())
    fills = eng.blotter.fills
    assert fills
    assert fills[0].price == pytest.approx(60.0)


def test_partial_fill_via_max_fill_qty():
    eng = OmsEngine(
        match=MatchConfig(commission_bps=0, slippage_bps=0, max_fill_qty=0.4,
                          fill_policy="same_bar_close")
    )
    o, h, l, c = _ohlc(5)
    order = eng.submit(
        {
            "side": OrderSide.BUY,
            "order_type": OrderType.MARKET,
            "qty": 1.0,
            "tif": TimeInForce.GTC,
        },
        bar_index=0,
    )
    eng._execute_order(order, i=0, fill_raw=float(c[0]), high=float(h[0]), low=float(l[0]))
    assert order.status == OrderStatus.PARTIAL
    assert order.filled_qty == pytest.approx(0.4)


def test_oco_cancels_sibling():
    eng = OmsEngine(match=MatchConfig(commission_bps=0, slippage_bps=0))
    entry, tp, sl = submit_bracket(
        eng,
        side=OrderSide.BUY,
        qty=1.0,
        take_profit=120.0,
        stop_loss=80.0,
        bar_index=0,
    )
    assert tp.oco_group == sl.oco_group > 0
    # simulate TP fill
    tp.status = OrderStatus.FILLED
    eng._cancel_oco_siblings(tp)
    assert sl.status == OrderStatus.CANCELED
    assert entry.status == OrderStatus.NEW


def test_replay_adapter_smoke():
    o, h, l, c = _ohlc(25)
    out = run_ohlc_replay(o, h, l, c, Idle(), initial_cash=10_000.0)
    assert out["ok"] is True
    assert out["work_checklist"]["replay_adapter"] is True
    assert out["work_checklist"]["gtc"] is True


def test_buffer_pool_and_shader_catalog():
    pool = BufferPool(max_slabs=2)
    a = pool.acquire(64)
    pool.release(a)
    b = pool.acquire(32)
    assert len(b) >= 32
    names = list_shaders()
    assert "oms_bar_match.metal" in names
    src = load_shader_source(names[0])
    assert "kernel" in src or "metal" in src.lower() or len(src) > 0
