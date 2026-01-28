from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from monte_neo.data.downloader import BinanceDownloader, download_sample_data


@pytest.fixture
def mock_spot():
    with patch("monte_neo.data.downloader.Spot") as mock:
        yield mock

def test_downloader_init(mock_spot):
    downloader = BinanceDownloader(api_key="test_key", api_secret="test_secret")
    assert downloader.api_key == "test_key"
    assert downloader.api_secret == "test_secret"
    mock_spot.assert_called_with(api_key="test_key", api_secret="test_secret")

def test_get_available_symbols(mock_spot):
    mock_instance = mock_spot.return_value
    mock_instance.exchange_info.return_value = {
        "symbols": [
            {"symbol": "BTCUSDT", "status": "TRADING"},
            {"symbol": "ETHUSDT", "status": "TRADING"},
            {"symbol": "BNBUSDT", "status": "BREAK"},
        ]
    }
    downloader = BinanceDownloader()
    symbols = downloader.get_available_symbols()
    assert symbols == ["BTCUSDT", "ETHUSDT"]

def test_fetch_klines_success(mock_spot):
    mock_instance = mock_spot.return_value
    # Mock two batches
    # Batch 1: 1000 candles, last close_time is 999
    batch1 = [[i, 1.0, 1.1, 0.9, 1.0, 100.0, i, 1000.0, 10, 50.0, 500.0, 0] for i in range(1000)]
    # Batch 2: 1 candle, close_time is 1001
    batch2 = [[1001, 1.0, 1.1, 0.9, 1.0, 100.0, 1001, 1000.0, 10, 50.0, 500.0, 0]]
    mock_instance.klines.side_effect = [batch1, batch2, []]
    
    downloader = BinanceDownloader()
    # end_ms is 1001
    klines = downloader._fetch_klines("BTCUSDT", "1h", 0, 1001)
    assert len(klines) == 1001
    assert mock_instance.klines.call_count == 2

def test_fetch_klines_rate_limit(mock_spot):
    mock_instance = mock_spot.return_value
    batch = [[0, 1.0, 1.1, 0.9, 1.0, 100.0, 1000, 1000.0, 10, 50.0, 500.0, 0]]
    mock_instance.klines.side_effect = [
        Exception("429: Too many requests"),
        batch,
        []
    ]
    
    downloader = BinanceDownloader()
    with patch("time.sleep") as mock_sleep:
        klines = downloader._fetch_klines("BTCUSDT", "1h", 0, 1000)
        assert len(klines) == 1
        mock_sleep.assert_any_call(10)

def test_fetch_klines_error(mock_spot):
    mock_instance = mock_spot.return_value
    mock_instance.klines.side_effect = Exception("Generic Error")
    
    downloader = BinanceDownloader()
    with pytest.raises(Exception, match="Generic Error"):
        downloader._fetch_klines("BTCUSDT", "1h", 0, 1000)

def test_download_basic(mock_spot):
    mock_instance = mock_spot.return_value
    # Return one kline that covers the whole range to avoid multiple calls
    start_ts = int(datetime.fromisoformat("2021-01-01").timestamp() * 1000)
    end_ts = int(datetime.fromisoformat("2021-01-02").timestamp() * 1000)
    
    kline = [start_ts, "1.0", "1.1", "0.9", "1.0", "100.0", end_ts, "1000.0", 10, "50.0", "500.0", "0"]
    mock_instance.klines.side_effect = [[kline], []]
    
    downloader = BinanceDownloader()
    callback = MagicMock()
    df = downloader.download(
        "BTCUSDT", "1h", "2021-01-01", "2021-01-02", progress_callback=callback
    )
    
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert "open" in df.columns
    assert df.index.name == "timestamp"
    callback.assert_called()

def test_download_invalid_timeframe(mock_spot):
    downloader = BinanceDownloader()
    with pytest.raises(ValueError, match="Invalid timeframe"):
        downloader.download("BTCUSDT", "invalid", "2021-01-01")

def test_download_multiple(mock_spot):
    mock_instance = mock_spot.return_value
    kline = [1609459200000, 1.0, 1.1, 0.9, 1.0, 100.0, 1609462799999, 1000.0, 10, 50.0, 500.0, 0]
    mock_instance.klines.return_value = [kline]
    
    downloader = BinanceDownloader()
    results = downloader.download_multiple(["BTCUSDT", "ETHUSDT"], "1h", "2021-01-01")
    assert len(results) == 2
    assert "BTCUSDT" in results
    assert "ETHUSDT" in results

def test_download_multiple_error(mock_spot):
    downloader = BinanceDownloader()
    # Mock download to raise exception for one symbol
    with patch.object(downloader, "download", side_effect=[Exception("Error"), pd.DataFrame()]):
        results = downloader.download_multiple(["BTCUSDT", "ETHUSDT"], "1h", "2021-01-01")
        assert len(results) == 1
        assert "ETHUSDT" in results

def test_download_sample_data(mock_spot):
    mock_instance = mock_spot.return_value
    kline = [1609459200000, 1.0, 1.1, 0.9, 1.0, 100.0, 1609462799999, 1000.0, 10, 50.0, 500.0, 0]
    mock_instance.klines.return_value = [kline]
    
    df = download_sample_data(days=1)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
