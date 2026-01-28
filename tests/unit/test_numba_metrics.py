import pytest
import numpy as np
from monte_neo.metrics.numba_funcs import (
    extract_trades_fast, 
    calculate_batch_fast,
    calculate_batch_multi_price_fast
)

@pytest.fixture
def sample_market_data():
    prices = np.array([100.0, 102.0, 101.0, 105.0, 104.0, 110.0])
    highs = prices + 1.0
    lows = prices - 1.0
    return prices, highs, lows

def test_extract_trades_fast(sample_market_data):
    prices, highs, lows = sample_market_data
    # Signal: 1 (buy at index 1), -1 (sell at index 3)
    signals = np.array([0, 1, 0, -1, 0, 0])
    
    trades = extract_trades_fast(
        prices, highs, lows, signals,
        use_sl_tp=False, commission_pct=0.01
    )
    
    assert len(trades) == 1
    entry_idx, exit_idx, entry_p, exit_p, pos, pnl, pnl_pct = trades[0]
    assert entry_idx == 1
    assert exit_idx == 3
    assert pos == 1
    assert pnl == (105.0 - 102.0)
    # pnl_pct = (3/102) - 0.01*2 = 0.0294 - 0.02 = 0.0094
    assert pnl_pct == pytest.approx((3.0/102.0) - 0.02)

def test_extract_trades_sl_tp(sample_market_data):
    prices, highs, lows = sample_market_data
    signals = np.array([1, 0, 0, 0, 0, 0])
    
    # Buy at 100, SL at 5% (95), TP at 2% (102)
    # High at index 1 is 103, so TP should be hit
    trades = extract_trades_fast(
        prices, highs, lows, signals,
        use_sl_tp=True, sl_pct=5.0, tp_pct=2.0
    )
    
    assert len(trades) == 1
    assert trades[0][3] == 102.0 # Exit at TP price

def test_calculate_batch_fast(sample_market_data):
    prices, highs, lows = sample_market_data
    signal_matrix = np.array([
        [0, 1, 0, -1, 0, 0], # Trade 1
        [1, 0, -1, 0, 1, -1], # Trade 2 & 3
    ])
    
    results = calculate_batch_fast(
        prices, highs, lows, signal_matrix,
        use_sl_tp=False, sl_pct=0, tp_pct=0
    )
    
    assert results.shape == (2, 4)
    assert results[0, 3] == 1 # n_trades
    assert results[1, 3] == 2 # n_trades

def test_calculate_batch_multi_price_fast():
    # 2 scenarios, 5 candles each
    prices = np.array([
        [100, 102, 104, 106, 108],
        [100, 98, 96, 94, 92]
    ], dtype=np.float64)
    highs = prices + 1
    lows = prices - 1
    signals = np.array([
        [1, 0, 0, 0, -1],
        [1, 0, 0, 0, -1]
    ])
    
    results = calculate_batch_multi_price_fast(
        prices, highs, lows, signals,
        use_sl_tp=False, sl_pct=0, tp_pct=0
    )
    
    assert results[0, 0] > 0 # Positive return for uptrend
    assert results[1, 0] < 0 # Negative return for downtrend
