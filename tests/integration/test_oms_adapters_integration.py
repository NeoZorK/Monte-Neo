"""Integration tests for OMS adapters."""

from __future__ import annotations

from monte_neo.oms import (
    OrderIntent,
    OrderSide,
    OrderType,
    make_adapter,
    reconcile_fills,
)


def test_binance_paper_cancel_and_reconcile() -> None:
    ad = make_adapter("binance", mode="paper", mid=100.0, commission_bps=0.0)
    far = ad.submit(
        OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            qty=1.0,
            limit_px=10.0,
        )
    )
    assert far.status == "NEW"
    assert ad.cancel(far.venue_order_id) is True
    filled = ad.submit(
        OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            qty=0.5,
        )
    )
    assert filled.status == "FILLED"
    venue = ad.poll_fills()
    local = [{"qty": f.qty, "price": f.price} for f in venue]
    assert reconcile_fills(local, venue)["ok"] is True
