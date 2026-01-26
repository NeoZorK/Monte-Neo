"""Binance WebSocket streaming utilities."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from binance.websocket.spot.websocket_stream import (
    SpotWebsocketStreamClient as WebsocketClient,
)

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


class BinanceWebsocketStreamer:
    """Stream Binance market data via WebSocket."""

    _LOWER_INTERVALS = {
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "6h",
        "8h",
        "12h",
        "1d",
        "3d",
        "1w",
    }
    _UPPER_INTERVALS = {"1M"}

    def __init__(
        self,
        stream_url: str | None = None,
        callback: Callable[[dict], None] | None = None,
    ) -> None:
        """Initialize WebSocket client.

        Args:
            stream_url: Optional WebSocket endpoint override.
            callback: Optional default handler for incoming messages.
        """
        self._callbacks: list[Callable[[dict], None]] = []
        if callback:
            self._callbacks.append(callback)
        self._client = WebsocketClient(
            stream_url=stream_url or "wss://stream.binance.com:9443",
            on_message=self._dispatch_message,
            on_error=self._handle_error,
        )
        self._started = False

    def __enter__(self) -> BinanceWebsocketStreamer:
        """Enter context manager."""
        self.start()
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        """Exit context manager."""
        self.stop()

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
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_interval = self._normalize_interval(interval)
        self._register_callback(callback)
        self.start()
        self._client.kline(
            symbol=normalized_symbol,
            interval=normalized_interval,
            id=stream_id,
        )

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
        normalized_symbol = self._normalize_symbol(symbol)
        self.start()
        self._register_callback(callback)
        self._client.mini_ticker(symbol=normalized_symbol, id=stream_id)

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
        normalized_streams = self._normalize_streams(streams)
        self.start()
        self._register_callback(callback)
        self._client.subscribe(stream=normalized_streams, id=stream_id)

    def _normalize_symbol(self, symbol: str) -> str:
        normalized = symbol.strip()
        if not normalized:
            raise ValueError("Symbol must be non-empty")
        return normalized.lower()

    def _normalize_interval(self, interval: str) -> str:
        normalized = interval.strip()
        if normalized in self._UPPER_INTERVALS:
            return normalized
        lower = normalized.lower()
        if lower in self._LOWER_INTERVALS:
            return lower
        raise ValueError(f"Unsupported interval: {interval}")

    def _normalize_streams(self, streams: list[str]) -> list[str]:
        if not streams:
            raise ValueError("Streams list must be non-empty")
        normalized = [stream.strip() for stream in streams]
        if any(not stream for stream in normalized):
            raise ValueError("Streams list contains empty stream")
        return normalized

    def _register_callback(self, callback: Callable[[dict], None]) -> None:
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def _dispatch_message(self, message: Any) -> None:
        if not self._callbacks:
            return
        if isinstance(message, dict):
            payload = message
        else:
            payload = {"message": message}
        for callback in self._callbacks:
            try:
                callback(payload)
            except Exception as exc:
                logger.exception("WebSocket callback error: %s", exc)

    def _handle_error(self, error: Any) -> None:
        logger.error("WebSocket error: %s", error)
