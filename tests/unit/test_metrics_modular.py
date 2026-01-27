"""Unit tests for modular metrics components."""

import numpy as np
import pytest

from monte_neo.metrics import numba_funcs, utils
from monte_neo.metrics.types import TradeResult


def test_trade_result_dataclass():
    """Test TradeResult dataclass."""
    t = TradeResult(
        entry_idx=0,
        exit_idx=10,
        entry_price=100.0,
        exit_price=110.0,
        direction=1,
        pnl=10.0,
        pnl_pct=0.1,
    )
    assert t.entry_idx == 0
    assert t.pnl == 10.0
    assert t.direction == 1


def test_metrics_utils():
    """Test utility functions."""
    # max_consecutive
    pnls = [10, 10, -5, 10, 10, 10, -5]
    assert utils.max_consecutive(pnls, wins=True) == 3
    assert utils.max_consecutive(pnls, wins=False) == 1

    # recovery_factor
    assert utils.calculate_recovery_factor(100.0, 0.5) == 200.0
    assert utils.calculate_recovery_factor(100.0, 0.0) == 0.0

    # calmar_ratio
    # avg_ret = 1.0, max_dd = 0.5, periods = 2
    # annual = 1.0 * 2 = 2.0. ratio = 2.0 / 0.5 = 4.0
    assert utils.calculate_calmar_ratio(1.0, 0.5, periods_per_year=2) == 4.0
    assert utils.calculate_calmar_ratio(1.0, 0.0) == 0.0


def test_numba_extract_trades_fast():
    """Test Numba trade extraction directly."""
    prices = np.array([100.0, 101.0, 99.0, 102.0, 105.0])
    highs = prices
    lows = prices
    signals = np.array([1, 0, 0, 0, -1])  # Long at 0, exit at 4 (signal flip)

    # Test basic extraction without SL/TP
    trades = numba_funcs.extract_trades_fast(
        prices, highs, lows, signals, use_sl_tp=False, sl_pct=0.0, tp_pct=0.0
    )
    assert len(trades) == 1
    # (entry_idx, exit_idx, entry_price, exit_price, position, pnl, pnl_pct)
    t = trades[0]
    assert t[0] == 0  # entry_idx
    assert t[1] == 4  # exit_idx
    assert t[2] == 100.0  # entry
    assert t[3] == 105.0  # exit
    assert t[4] == 1  # long
    assert t[5] == 5.0  # pnl


def test_numba_calculate_batch_fast():
    """Test Numba batch calculation directly."""
    prices = np.array([100.0, 105.0, 100.0])
    highs = prices
    lows = prices
    
    # 2 signals: one trades, one doesn't
    signal_matrix = np.zeros((2, 3), dtype=np.int32)
    signal_matrix[0] = [1, 0, -1] # Long at 0, exit at 2. Entry 100, Exit 100 -> PnL 0
    # Actually wait: index 0 (100), index 1 (105), index 2 (100).
    # Signal: 0=Buy, 1=Hold, 2=Sell.
    # Entry at 0 (100). Exit at 2 (100). PnL = 0.
    
    results = numba_funcs.calculate_batch_fast(
        prices, highs, lows, signal_matrix, use_sl_tp=False, sl_pct=0.0, tp_pct=0.0
    )
    
    # results shape (2, 4): total_return, max_dd, pf, n_trades
    assert results.shape == (2, 4)
    assert results[0, 3] == 1 # 1 trade
    assert results[1, 3] == 0 # 0 trades
