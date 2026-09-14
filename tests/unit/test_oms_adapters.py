"""Unit tests for OMS venue adapters (paper + live gates)."""

from __future__ import annotations

import pytest

from monte_neo.oms import (
    BinanceAdapter,
    BybitAdapter,
    OrderIntent,
    OrderSide,
    OrderType,
    PaperExchangeAdapter,
    make_adapter,
    reconcile_fills,
)


def test_paper_exchange_market_fill() -> None:
    ad = PaperExchangeAdapter(mid=100.0, commission_bps=5.0, initial_cash=10_000.0)
    rep = ad.submit(
        OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            qty=0.1,
        )
    )
    assert rep.status == "FILLED"
    fills = ad.poll_fills()
    assert len(fills) >= 1
    assert ad.get_positions()["BTCUSDT"] > 0.0
    assert ad.get_balances()["cash"] < 10_000.0


def test_paper_limit_far_stays_new() -> None:
    ad = PaperExchangeAdapter(mid=100.0, commission_bps=0.0)
    rep = ad.submit(
        OrderIntent(
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            qty=1.0,
            limit_px=50.0,
        )
    )
    assert rep.status == "NEW"
    assert ad.poll_fills() == []


def test_make_adapter_binance_paper() -> None:
    ad = make_adapter("binance", mode="paper", mid=200.0)
    assert isinstance(ad, BinanceAdapter)
    assert ad.work_checklist()["paper"] is True
    rep = ad.submit(
        OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            qty=0.01,
        )
    )
    assert rep.status == "FILLED"


def test_make_adapter_bybit_paper() -> None:
    ad = make_adapter("bybit", mode="paper", mid=150.0)
    assert isinstance(ad, BybitAdapter)
    assert ad.work_checklist()["venue_bybit"] is True


def test_binance_live_blocked_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MONTE_NEO_LIVE_TRADING", raising=False)
    with pytest.raises(RuntimeError, match="LIVE_TRADING"):
        BinanceAdapter(mode="live", api_key="k", api_secret="s")


def test_binance_live_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONTE_NEO_LIVE_TRADING", "1")
    monkeypatch.setenv("MONTE_NEO_LIVE_DRY_RUN", "1")
    ad = BinanceAdapter(mode="live", api_key="k", api_secret="s", mid=100.0)
    rep = ad.submit(
        OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            qty=0.01,
        )
    )
    assert rep.raw.get("dry_run") is True
    assert len(ad.dry_run_log()) == 1
    assert ad.work_checklist()["dry_run"] is True


def test_bybit_live_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONTE_NEO_LIVE_TRADING", "1")
    with pytest.raises(RuntimeError, match="BYBIT_API"):
        BybitAdapter(mode="live", api_key="", api_secret="")


def test_reconcile_fills_ok() -> None:
    ad = PaperExchangeAdapter(mid=100.0, commission_bps=0.0)
    ad.submit(
        OrderIntent(
            symbol="X",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            qty=1.0,
        )
    )
    venue = ad.poll_fills()
    local = [{"qty": f.qty, "price": f.price} for f in venue]
    out = reconcile_fills(local, venue)
    assert out["ok"] is True
