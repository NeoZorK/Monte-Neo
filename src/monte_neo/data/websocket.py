"""Binance WebSocket streaming utilities."""

from __future__ import annotations

from collections.abc import Callable

from binance.websocket.spot.websocket_client import SpotWebsocketClient as WebsocketClient


class BinanceWebsocketStreamer:
    """Stream Binance market data via WebSocket."""

    def __init__(self, stream_url: str | None = None) -> None:
        """Initialize WebSocket client.

        Args:
            stream_url: Optional WebSocket endpoint override.
        """
        self._client = (
            WebsocketClient(stream_url=stream_url) if stream_url else WebsocketClient()
        )
        self._started = False

    def start(self) -> None:
        """Start WebSocket connection."""
        if not self._started:
            self._client.start()
            self._started = True

    def stop(self) -> None:
        """Stop WebSocket connection."""
        if self._started:
            try:
                self._client.stop()
            finally:
                self._started = False

    def subscribe_kline(
        self,
        symbol: str,
        interval: str,
        callback: Callable[[dict], None],
        stream_id: int = 1,
    ) -> None:
        """Subscribe to kline stream.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT').
            interval: Candle interval (e.g., '1m', '1h').
            callback: Handler for incoming messages.
            stream_id: Client message id.
        """
        self.start()
        stream = f"{symbol.lower()}@kline_{interval}"
        self._client.instant_subscribe(stream=[stream], id=stream_id, callback=callback)

    def subscribe_mini_ticker(
        self,
        symbol: str,
        callback: Callable[[dict], None],
        stream_id: int = 2,
    ) -> None:
        """Subscribe to mini ticker stream.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT').
            callback: Handler for incoming messages.
            stream_id: Client message id.
        """
        self.start()
        self._client.mini_ticker(
            symbol=symbol.lower(),
            id=stream_id,
            callback=callback,
        )

    def subscribe_streams(
        self,
        streams: list[str],
        callback: Callable[[dict], None],
        stream_id: int = 3,
    ) -> None:
        """Subscribe to multiple raw stream names.

        Args:
            streams: Raw stream names (e.g., ['btcusdt@trade']).
            callback: Handler for incoming messages.
            stream_id: Client message id.
        """
        self.start()
        self._client.instant_subscribe(stream=streams, id=stream_id, callback=callback)

