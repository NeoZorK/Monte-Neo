"""Tests for Binance WebSocket streamer."""

from __future__ import annotations

import pytest

from monte_neo.data import websocket as ws_module
from monte_neo.data.websocket import BinanceWebsocketStreamer


class DummyWebsocketClient:
    """Dummy WebSocket client for testing."""

    instances: list[DummyWebsocketClient] = []

    def __init__(self, *args, **kwargs) -> None:
        self.calls: list[tuple] = []
        self.on_message = kwargs.get("on_message")
        self.on_error = kwargs.get("on_error")
        DummyWebsocketClient.instances.append(self)

    def start(self) -> None:
        self.calls.append(("start",))

    def stop(self) -> None:
        self.calls.append(("stop",))

    def kline(self, symbol, interval, id=None, action=None) -> None:
        self.calls.append(("kline", symbol, interval, id, action))

    def mini_ticker(self, symbol=None, id=None, action=None, **kwargs) -> None:
        self.calls.append(("mini_ticker", symbol, id, action))

    def subscribe(self, stream, id=None) -> None:
        self.calls.append(("subscribe", stream, id))


def _setup_dummy(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[BinanceWebsocketStreamer, DummyWebsocketClient]:
    """Setup dummy WebSocket client and return streamer and instance."""
    DummyWebsocketClient.instances = []
    monkeypatch.setattr(ws_module, "WebsocketClient", DummyWebsocketClient)
    streamer = BinanceWebsocketStreamer()
    return streamer, DummyWebsocketClient.instances[0]


def test_subscribe_kline_builds_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """Builds kline stream and subscribes."""
    streamer, dummy = _setup_dummy(monkeypatch)

    def handler(message: dict) -> None:
        pass

    streamer.subscribe_kline(symbol="BTCUSDT", interval="1m", callback=handler)

    assert dummy.calls[0] == ("start",)
    assert dummy.calls[1][0] == "kline"
    assert dummy.calls[1][1] == "btcusdt"
    assert dummy.calls[1][2] == "1m"


def test_subscribe_mini_ticker_normalizes_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalizes symbol for mini ticker."""
    streamer, dummy = _setup_dummy(monkeypatch)

    def handler(message: dict) -> None:
        pass

    streamer.subscribe_mini_ticker(symbol="EthUsdt", callback=handler)

    assert dummy.calls[0] == ("start",)
    assert dummy.calls[1][0] == "mini_ticker"
    assert dummy.calls[1][1] == "ethusdt"


def test_invalid_interval_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raises on unsupported interval."""
    streamer, _ = _setup_dummy(monkeypatch)

    def handler(message: dict) -> None:
        pass

    with pytest.raises(ValueError):
        streamer.subscribe_kline(symbol="BTCUSDT", interval="bad", callback=handler)


def test_context_manager_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stops client on context exit."""
    streamer, dummy = _setup_dummy(monkeypatch)

    def handler(message: dict) -> None:
        pass

    with streamer:
        streamer.subscribe_mini_ticker(symbol="BTCUSDT", callback=handler)

    assert ("stop",) in dummy.calls
