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
    # Now we use subscribe directly
    assert dummy.calls[1][0] == "subscribe"
    assert dummy.calls[1][1] == "btcusdt@kline_1m"


def test_subscribe_mini_ticker_normalizes_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalizes symbol for mini ticker."""
    streamer, dummy = _setup_dummy(monkeypatch)

    def handler(message: dict) -> None:
        pass

    streamer.subscribe_mini_ticker(symbol="EthUsdt", callback=handler)

    assert dummy.calls[0] == ("start",)
    # Now we use subscribe directly
    assert dummy.calls[1][0] == "subscribe"
    assert dummy.calls[1][1] == "ethusdt@miniTicker"


def test_reconnect_resubscribes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that reconnect logic resubscribes to active streams."""
    # Mock time.sleep to avoid waiting
    monkeypatch.setattr(ws_module.time, "sleep", lambda x: None)
    
    streamer, dummy = _setup_dummy(monkeypatch)

    def handler(message: dict) -> None:
        pass

    # Subscribe to populate active streams
    streamer.subscribe_kline(symbol="BTCUSDT", interval="1m", callback=handler)
    
    # Clear calls to track reconnect actions
    dummy.calls = []
    
    # Trigger reconnect via error handler
    # Error handler calls _attempt_reconnect
    # _attempt_reconnect calls stop (try), start, subscribe
    streamer._handle_error(Exception("Connection lost"))

    # Verify sequence: stop -> start -> subscribe
    # Note: stop is called inside try/except, so it might appear
    
    # Filter for relevant calls
    actions = [call[0] for call in dummy.calls]
    assert "start" in actions
    assert "subscribe" in actions
    
    # Verify subscription restoration
    subscribe_calls = [call for call in dummy.calls if call[0] == "subscribe"]
    assert len(subscribe_calls) > 0
    # The stream list might be passed as a list, check content
    streams = subscribe_calls[0][1]
    assert "btcusdt@kline_1m" in streams


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
