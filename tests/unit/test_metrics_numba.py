import pytest
import numpy as np
from monte_neo.metrics.numba_funcs import (
    extract_trades_fast, 
    calculate_batch_fast,
    calculate_batch_multi_price_fast
)

def test_extract_trades_fast_basic():
    prices = np.array([100, 101, 102, 101, 100], dtype=np.float64)
    highs = prices + 0.5
    lows = prices - 0.5
    signals = np.array([1, 0, 0, -1, 0], dtype=np.int32)
    
    trades = extract_trades_fast(prices, highs, lows, signals)
    assert len(trades) == 1
    # (entry_idx, exit_idx, entry_price, exit_price, position, pnl, pnl_pct)
    assert trades[0][0] == 0
    assert trades[0][1] == 3
    assert trades[0][4] == 1 # Long
    assert trades[0][5] == 1.0 # 101 - 100

def test_extract_trades_fast_sl_tp():
    prices = np.array([100, 101, 105, 100, 95], dtype=np.float64)
    highs = prices + 0.1
    lows = prices - 0.1
    signals = np.array([1, 0, 0, 0, 0], dtype=np.int32)
    
    # TP hit at index 2 (5%)
    trades = extract_trades_fast(prices, highs, lows, signals, use_sl_tp=True, tp_pct=4.0, sl_pct=2.0)
    assert len(trades) == 1
    assert trades[0][1] == 2
    assert trades[0][5] > 0
    
    # SL hit at index 4 (5%)
    signals2 = np.array([1, 0, 0, 0, 0], dtype=np.int32)
    prices2 = np.array([100, 101, 101, 101, 95], dtype=np.float64)
    highs2 = prices2 + 0.1
    lows2 = prices2 - 0.1
    trades2 = extract_trades_fast(prices2, highs2, lows2, signals2, use_sl_tp=True, tp_pct=10.0, sl_pct=2.0)
    assert len(trades2) == 1
    assert trades2[0][1] == 4
    assert trades2[0][5] < 0

def test_extract_trades_fast_comm_slip():
    prices = np.array([100, 105], dtype=np.float64)
    highs = prices + 0.1
    lows = prices - 0.1
    signals = np.array([1, -1], dtype=np.int32)
    
    # 1% slippage, 1% commission
    # Entry: 100 * (1 + 0.01) = 101
    # Exit: 105 * (1 - 0.01) = 103.95
    # PnL: 103.95 - 101 = 2.95
    # PnL %: (2.95 / 101) - 0.02 = 0.029207 - 0.02 = 0.009207
    trades = extract_trades_fast(prices, highs, lows, signals, commission_pct=0.01, slippage_pct=0.01)
    assert len(trades) == 1
    assert trades[0][2] == 101.0
    assert trades[0][3] == 105.0 # exit_price is the original price, adj happens in pnl calculation
    assert trades[0][6] == pytest.approx(0.0092079, abs=1e-5)

def test_calculate_batch_fast():
    prices = np.array([100, 102, 104, 106, 108], dtype=np.float64)
    highs = prices + 0.5
    lows = prices - 0.5
    signal_matrix = np.array([[1, 0, -1, 0, 0], [0, 1, 0, -1, 0]], dtype=np.int32)
    
    results = calculate_batch_fast(prices, highs, lows, signal_matrix, False, 0.0, 0.0, 0.0, 0.0)
    assert results.shape == (2, 4) # (n_signals, n_metrics)
    # Metrics: [total_return, max_dd, pf, n_trades]
    assert results[0, 0] > 0 # Total return for first signal
    assert results[1, 0] > 0 # Total return for second signal
    assert results[0, 3] == 1 # One trade

def test_calculate_batch_multi_price_fast():
    price_matrix = np.array([
        [100, 105, 110, 0, 0],
        [100, 95, 90, 0, 0]
    ], dtype=np.float64)
    high_matrix = price_matrix + 1
    low_matrix = price_matrix - 1
    signal_matrix = np.array([
        [1, 0, -1, 0, 0],
        [1, 0, -1, 0, 0]
    ], dtype=np.int32)
    
    results = calculate_batch_multi_price_fast(
        price_matrix, high_matrix, low_matrix, signal_matrix, 
        False, 0.0, 0.0, 0.0, 0.0
    )
    assert results.shape == (2, 4)
    assert results[0, 0] > 0 # Row 1 profit
    assert results[1, 0] < 0 # Row 2 loss
    assert results[0, 3] == 1
    assert results[1, 3] == 1
