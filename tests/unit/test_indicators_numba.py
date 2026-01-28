
import pytest
import numpy as np
from monte_neo.indicators.numba_funcs import (
    sma_numba, 
    ema_numba, 
    rsi_numba, 
    sma_crossover_signals_numba,
    rsi_signals_numba,
    macd_signals_numba
)

def test_sma_numba():
    data = np.array([10, 20, 30, 40, 50], dtype=np.float64)
    res = sma_numba(data, 3)
    assert len(res) == 5
    assert np.isnan(res[0])
    assert np.isnan(res[1])
    assert res[2] == 20.0
    assert res[3] == 30.0
    assert res[4] == 40.0

def test_ema_numba():
    data = np.array([10, 20, 30, 40, 50], dtype=np.float64)
    res = ema_numba(data, 3)
    assert len(res) == 5
    assert res[0] == 10.0
    # alpha = 2 / (3 + 1) = 0.5
    # EMA[1] = (20 - 10) * 0.5 + 10 = 15.0
    assert res[1] == pytest.approx(15.0)
    # EMA[2] = (30 - 15) * 0.5 + 15 = 22.5
    assert res[2] == pytest.approx(22.5)

def test_rsi_numba():
    # Simple data with known RSI
    data = np.array([100, 110, 100, 110, 100, 110, 100, 110, 100, 110, 100, 110, 100, 110, 100], dtype=np.float64)
    res = rsi_numba(data, 14)
    assert len(res) == 15
    assert not np.isnan(res[14])
    assert 40 < res[14] < 60

def test_sma_crossover_signals_numba():
    # Data with a clear crossover
    # Prices: 10, 10, 10, 10, 10, 20, 20, 20, 20, 20
    # Fast (2): [nan, 10, 10, 10, 10, 15, 20, 20, 20, 20]
    # Slow (5): [nan, nan, nan, nan, 10, 12, 14, 16, 18, 20]
    data = np.array([10, 10, 10, 10, 10, 20, 20, 20, 20, 20], dtype=np.float64)
    res = sma_crossover_signals_numba(data, 2, 5)
    assert len(res) == 10
    # Crossover happens at index 5 (fast 15 > slow 12)
    assert res[5] == 1.0
    assert np.any(res == 1.0)

def test_rsi_signals_numba():
    data = np.array([100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200], dtype=np.float64)
    res = rsi_signals_numba(data, 5, 30, 70)
    assert len(res) == 11
    # RSI will be very high, should give -1 (overbought)
    assert -1.0 in res

def test_macd_signals_numba():
    data = np.array([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115], dtype=np.float64)
    res = macd_signals_numba(data, 3, 6, 3)
    assert len(res) == 16
    assert np.any(res != 0)
