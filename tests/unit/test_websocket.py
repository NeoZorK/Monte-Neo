from unittest.mock import MagicMock, patch

import pytest

from monte_neo.data.websocket import BinanceWebsocketStreamer


@pytest.fixture
def streamer():
    with patch("monte_neo.data.websocket.WebsocketClient") as mock_client:
        # Give the mock client start/stop/subscribe methods
        instance = mock_client.return_value
        instance.start = MagicMock()
        instance.stop = MagicMock()
        instance.subscribe = MagicMock()
        instance.kline = MagicMock()
        yield BinanceWebsocketStreamer()

def test_streamer_init(streamer):
    assert streamer._callbacks == []
    assert streamer._started is False

def test_streamer_start_stop(streamer):
    streamer.start()
    assert streamer._started is True
    streamer.stop()
    assert streamer._started is False

def test_streamer_dispatch_message(streamer):
    mock_cb = MagicMock()
    streamer._callbacks.append(mock_cb)
    
    msg = {"e": "kline", "s": "BTCUSDT"}
    streamer._dispatch_message(None, msg)
    
    mock_cb.assert_called_once_with(msg)

def test_streamer_subscribe_kline(streamer):
    mock_cb = MagicMock()
    with patch.object(streamer._client, "subscribe") as mock_subscribe:
        streamer.subscribe_kline("BTCUSDT", "1m", mock_cb)
        assert mock_subscribe.called
        assert "btcusdt@kline_1m" in streamer._active_streams
