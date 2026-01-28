
import numpy as np
import pandas as pd
import pytest

from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.metrics.types import TradeResult


def test_initial_capital_equity_curve():
    """Test that equity curve starts with initial capital and calculates correctly."""
    initial_capital = 100000.0
    calc = MetricsCalculator(initial_capital=initial_capital, leverage=1.0)
    
    # Mock trades: 1% profit, then 1% loss
    trades = [
        TradeResult(entry_idx=0, exit_idx=1, entry_price=100.0, exit_price=101.0, direction=1, pnl=1.0, pnl_pct=0.01),
        TradeResult(entry_idx=2, exit_idx=3, entry_price=100.0, exit_price=99.0, direction=1, pnl=-1.0, pnl_pct=-0.01)
    ]
    
    equity = calc._calculate_equity(trades)
    
    # Expected: [100000, 101000, 99990]
    # 100000 * 1.01 = 101000
    # 101000 * 0.99 = 99990
    assert len(equity) == 3
    assert equity[0] == initial_capital
    assert pytest.approx(equity[1]) == 101000.0
    assert pytest.approx(equity[2]) == 99990.0

def test_leverage_effect():
    """Test that leverage correctly scales returns."""
    initial_capital = 100000.0
    leverage = 2.0
    calc = MetricsCalculator(initial_capital=initial_capital, leverage=leverage)
    
    # Mock trade: 1% profit
    trades = [
        TradeResult(entry_idx=0, exit_idx=1, entry_price=100.0, exit_price=101.0, direction=1, pnl=1.0, pnl_pct=0.01)
    ]
    
    equity = calc._calculate_equity(trades)
    
    # Expected: [100000, 102000] (1% * 2 leverage = 2% gain)
    assert len(equity) == 2
    assert equity[0] == initial_capital
    assert pytest.approx(equity[1]) == 102000.0

def test_absolute_profit_metrics():
    """Test calculation of total_profit_abs and final_balance."""
    initial_capital = 100000.0
    calc = MetricsCalculator(initial_capital=initial_capital, leverage=1.0)
    
    # Mock trade: 10% profit
    trades = [
        TradeResult(entry_idx=0, exit_idx=1, entry_price=100.0, exit_price=110.0, direction=1, pnl=10.0, pnl_pct=0.1)
    ]
    
    # We need to mock data and signals to use calculate_all,
    # but since we already tested _calculate_equity, let's test if calculate_all includes these metrics.
    
    data = pd.DataFrame({
        "open": [100, 100], "high": [110, 110], "low": [90, 90], "close": [100, 110], "volume": [100, 100]
    })
    signals = np.array([0, 1]) # Entry at idx 1 (close of first candle)
    # Actually signals array should be same length as data
    # _extract_trades logic: signals[i] is signal at end of bar i
    
    # Simple test with calculate_all might be complex to setup perfectly due to trade extraction.
    # Let's just check if the metrics are present in the returned dict.
    
    # Mocking _extract_trades to return our fixed trade
    from unittest.mock import MagicMock
    calc._extract_trades = MagicMock(return_value=trades)
    
    metrics = calc.calculate_all(data, signals, required_metrics=["total_profit_abs", "final_balance"])
    
    assert metrics["final_balance"] == pytest.approx(110000.0)
    assert metrics["total_profit_abs"] == pytest.approx(10000.0)
