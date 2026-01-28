import pytest
import pandas as pd
import numpy as np
from monte_neo.indicators.technical_lib import TechnicalIndicators

@pytest.fixture
def sample_data():
    return pd.Series([10.0, 11.0, 12.0, 13.0, 14.0])

@pytest.fixture
def ohlc_data():
    return pd.DataFrame({
        "high": [11, 12, 13, 14, 15],
        "low": [9, 10, 11, 12, 13],
        "close": [10, 11, 12, 13, 14]
    })

def test_sma(sample_data):
    res = TechnicalIndicators.sma(sample_data, 3)
    assert res.iloc[2] == 11.0

def test_ema(sample_data):
    res = TechnicalIndicators.ema(sample_data, 3)
    assert len(res) == 5

def test_rsi(sample_data):
    res = TechnicalIndicators.rsi(sample_data, 2)
    assert len(res) == 5

def test_macd(sample_data):
    m, s, h = TechnicalIndicators.macd(sample_data)
    assert len(m) == 5

def test_bollinger_bands(sample_data):
    u, m, l = TechnicalIndicators.bollinger_bands(sample_data, 3)
    assert len(u) == 5

def test_atr(ohlc_data):
    res = TechnicalIndicators.atr(ohlc_data, 3)
    assert len(res) == 5

def test_stochastic(ohlc_data):
    k, d = TechnicalIndicators.stochastic(ohlc_data, 3)
    assert len(k) == 5
