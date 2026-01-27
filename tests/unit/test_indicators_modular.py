"""Unit tests for modular indicator components."""

import numpy as np
import pytest

from monte_neo.indicators import numba_funcs


def test_sma_numba():
    """Test Numba SMA calculation."""
    data = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

    # Period 3
    # [nan, nan, 20, 30, 40]
    res = numba_funcs.sma_numba(data, 3)

    assert np.isnan(res[0])
    assert np.isnan(res[1])
    assert res[2] == 20.0
    assert res[3] == 30.0
    assert res[4] == 40.0


def test_ema_numba():
    """Test Numba EMA calculation."""
    data = np.array([10.0, 20.0])
    # Period 1 -> alpha = 1.0. EMA(1) = Price.
    # Period 2 -> alpha = 2/3.
    # EMA[0] = 10.
    # EMA[1] = (20 - 10)*2/3 + 10 = 10*0.666 + 10 = 16.666

    res = numba_funcs.ema_numba(data, 2)
    assert res[0] == 10.0
    assert res[1] == pytest.approx(16.666666)


def test_rsi_numba():
    """Test Numba RSI calculation."""
    # Simple case: Up 10, Up 10, Up 10.
    # Period 2.
    # data: [100, 110, 120, 130]
    # diff: [10, 10, 10]
    # idx 1, 2: gain=10, 10. avg_gain=10. avg_loss=0. RS=inf. RSI=100.

    data = np.array([100.0, 110.0, 120.0, 130.0])
    res = numba_funcs.rsi_numba(data, 2)

    # idx 0, 1: undefined (period=2)
    # Actually my implementation returns nan for <= period?
    # rsi_numba checks n <= period return nan.
    # Here n=4, period=2.
    # idx 0, 1: NaN.
    # idx 2: First RSI value.

    assert np.isnan(res[0])
    assert np.isnan(res[1])
    assert res[2] == 100.0
    assert res[3] == 100.0

    # Case with loss
    # [100, 90, 80] -> RSI = 0
    data_loss = np.array([100.0, 90.0, 80.0])
    res_loss = numba_funcs.rsi_numba(data_loss, 2)
    assert res_loss[2] == 0.0


def test_sma_crossover_signals_numba():
    """Test SMA crossover signals."""
    # Fast=2, Slow=4
    # data: [10, 10, 10, 10, 20, 20, 20, 20]
    # i=0..3: init.
    # i=4: fast(3,4)=15, slow(1,2,3,4)=12.5. Fast > Slow. Cross UP -> 1.

    data = np.array([10, 10, 10, 10, 20, 20, 20, 20], dtype=np.float64)
    res = numba_funcs.sma_crossover_signals_numba(data, 2, 4)

    # Expect 0s until index 4
    # At index 4: fast avg of data[3], data[4] = (10+20)/2 = 15
    # Slow avg of data[1..4] = (10+10+10+20)/4 = 12.5
    # Fast > Slow. Prev state (from init): Fast(10,10)=10, Slow(10,10,10,10)=10.
    # Wait, init is i=0..1 for fast, 0..3 for slow.
    # Init fast sum: data[0]+data[1] = 20. sma=10.
    # Init slow sum: data[0]..data[3] = 40. sma=10.
    # State: 10 > 10? No. -1.

    # i=4: fast sum 20 - 10 + 20 = 30. sma=15.
    # slow sum 40 - 10 + 20 = 50. sma=12.5.
    # State: 15 > 12.5 -> 1.
    # Change -1 -> 1. Signal 1.

    assert res[4] == 1.0
