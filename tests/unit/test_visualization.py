import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from monte_neo.visualization.charts import ChartGenerator

@pytest.fixture
def sample_ohlc():
    dates = pd.date_range("2023-01-01", periods=10)
    data = {
        "open": np.random.randn(10) + 100,
        "high": np.random.randn(10) + 102,
        "low": np.random.randn(10) + 98,
        "close": np.random.randn(10) + 100,
        "volume": np.random.randn(10) * 1000
    }
    return pd.DataFrame(data, index=dates)

def test_chart_generator_init():
    gen = ChartGenerator()
    assert hasattr(gen, "_has_mplfinance")

@patch("plotext.show")
@patch("plotext.candlestick")
def test_plot_candlestick_terminal(mock_candlestick, mock_show, sample_ohlc):
    gen = ChartGenerator()
    gen._has_mplfinance = False
    gen.plot_candlestick(sample_ohlc, title="Test Chart")
    
    assert mock_candlestick.called
    assert mock_show.called

@patch("plotext.show")
@patch("plotext.scatter")
def test_plot_with_signals(mock_scatter, mock_show, sample_ohlc):
    gen = ChartGenerator()
    signals = pd.Series([0] * 10, index=sample_ohlc.index)
    signals.iloc[2] = 1 # Buy
    signals.iloc[5] = -1 # Sell
    
    gen.plot_with_signals(sample_ohlc, signals)
    
    # Check if scatter was called for signals
    assert mock_scatter.call_count == 2
    assert mock_show.called
