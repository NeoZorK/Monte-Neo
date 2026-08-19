import numpy as np
import pytest

from monte_neo.indicators.numba_funcs import ema_numba, rsi_numba, sma_crossover_signals_numba, sma_numba


def test_sma_numba():
    data = np.array([10.0, 12.0, 14.0, 16.0, 18.0])
    # SMA 3: (10+12+14)/3=12, (12+14+16)/3=14, (14+16+18)/3=16
    res = sma_numba(data, 3)
    assert np.isnan(res[0])
    assert np.isnan(res[1])
    assert res[2] == pytest.approx(12.0)
    assert res[3] == pytest.approx(14.0)
    assert res[4] == pytest.approx(16.0)

def test_ema_numba():
    data = np.array([10.0, 20.0, 30.0])
    # alpha = 2 / (2+1) = 0.666...
    # res[0] = 10
    # res[1] = (20-10)*0.666 + 10 = 16.666
    res = ema_numba(data, 2)
    assert res[0] == 10.0
    assert res[1] == pytest.approx(16.6666666)

def test_rsi_numba():
    data = np.array([100.0, 102.0, 104.0, 102.0, 100.0])
    res = rsi_numba(data, 2)
    assert len(res) == 5
    assert not np.isnan(res[2])

def test_sma_crossover_signals_numba():
    # Price crosses up SMA 3 vs SMA 5 (simplified)
    data = np.linspace(100, 110, 20)
    res = sma_crossover_signals_numba(data, 3, 5)
    assert len(res) == 20
    assert res.dtype == np.float32
