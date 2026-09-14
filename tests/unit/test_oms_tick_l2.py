"""Unit tests for OMS tick/L2 lane."""

from __future__ import annotations

import numpy as np

from monte_neo.oms import (
    OrderSide,
    OrderType,
    TickL2Engine,
    book_from_mid,
    run_tick_l2_market_buy,
    synthetic_ticks,
    ticks_to_ohlc,
)
from monte_neo.oms.accel.match_l2_numba import walk_book_market
from monte_neo.oms.l2_match import L2MatchConfig, match_market_l2
from monte_neo.oms.types import Order


def test_synthetic_ticks_and_ohlc() -> None:
    ticks = synthetic_ticks(2_000, seed=1)
    ohlc = ticks_to_ohlc(ticks, bars=20)
    assert ohlc["close"].shape == (20,)
    assert np.all(ohlc["high"] >= ohlc["low"])


def test_book_from_mid_spread() -> None:
    book = book_from_mid(100.0, spread_bps=10.0, depth=3)
    assert book.best_ask() > book.best_bid()
    assert book.depth() == 3


def test_numba_walk_matches_python_l2() -> None:
    book = book_from_mid(100.0, spread_bps=4.0, depth=5, size=2.0)
    order = Order(
        order_id=1,
        symbol="SYM",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=3.0,
    )
    cfg = L2MatchConfig(commission_bps=5.0, slippage_bps=0.0, max_levels=5)
    slices = match_market_l2(order, book, cfg)
    py_qty = sum(s.qty for s in slices)
    py_notional = sum(s.qty * s.price for s in slices)
    py_fee = sum(s.fee for s in slices)
    py_vwap = py_notional / py_qty
    bid_px, bid_sz, ask_px, ask_sz = book.to_arrays(5)
    filled, vwap, fee, _ = walk_book_market(
        1, 3.0, bid_px, bid_sz, ask_px, ask_sz, 5.0, 0.0
    )
    assert abs(filled - py_qty) < 1e-9
    assert abs(vwap - py_vwap) < 1e-9
    assert abs(fee - py_fee) < 1e-9


def test_tick_l2_market_buy_fills() -> None:
    ticks = synthetic_ticks(500, seed=7)
    out = run_tick_l2_market_buy(
        ticks, qty=1.0, commission_bps=5.0, device="cpu_numba", initial_cash=50_000.0
    )
    assert out["ok"] is True
    assert out["lane"] == "oms_tick_l2"
    assert out["work_checklist"]["l2_matching"] is True
    assert out["blotter"]["n_fills"] >= 1
    assert out["account"]["positions"]["SYM"]["qty"] > 0.0


def test_limit_rests_until_marketable() -> None:
    ticks = synthetic_ticks(200, seed=2, start_px=100.0, vol=0.0)
    eng = TickL2Engine(
        l2=L2MatchConfig(commission_bps=0.0),
        device="cpu_numba",
        use_numba_walk=False,
        initial_cash=10_000.0,
    )
    eng.submit_limit(OrderSide.BUY, qty=1.0, limit_px=50.0, tag="far")
    out = eng.run_ticks(ticks)
    assert out["blotter"]["n_fills"] == 0
