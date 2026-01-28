import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch, PropertyMock
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.metrics.types import TradeResult

@pytest.fixture
def calculator():
    return MetricsCalculator()

@pytest.fixture
def sample_data():
    return pd.DataFrame({
        "open": [100, 101, 102, 103, 104],
        "high": [101, 102, 103, 104, 105],
        "low": [99, 100, 101, 102, 103],
        "close": [100.5, 101.5, 102.5, 103.5, 104.5]
    })

@pytest.fixture
def sample_signals():
    return pd.DataFrame({
        "signal": [1, 0, -1, 0, 1]
    })

def test_init():
    calc = MetricsCalculator(risk_free_rate=0.01, initial_capital=50000, leverage=2.0)
    assert calc.risk_free_rate == 0.01
    assert calc.initial_capital == 50000
    assert calc.leverage == 2.0

def test_calculate_all_empty(calculator, sample_data):
    signals = pd.DataFrame({"signal": [0, 0, 0, 0, 0]})
    res = calculator.calculate_all(sample_data, signals)
    assert res["trade_count"] == 0
    assert res["total_return"] == 0.0

def test_calculate_all_basic(calculator, sample_data, sample_signals):
    # Mock _extract_trades to return controlled trades
    trades = [
        TradeResult(0, 1, 100.0, 102.0, 1, 2.0, 0.02),
        TradeResult(2, 3, 102.0, 101.0, -1, 1.0, 0.01)
    ]
    with patch.object(calculator, "_extract_trades", return_value=trades):
        res = calculator.calculate_all(sample_data, sample_signals)
        assert res["trade_count"] == 2
        assert res["total_return"] == pytest.approx(0.03)
        assert "profit_factor" in res
        assert "sharpe_ratio" in res

def test_calculate_all_required_metrics(calculator, sample_data, sample_signals):
    trades = [TradeResult(0, 1, 100.0, 102.0, 1, 2.0, 0.02)]
    with patch.object(calculator, "_extract_trades", return_value=trades):
        res = calculator.calculate_all(sample_data, sample_signals, required_metrics=["trade_count", "winrate"])
        assert len(res) == 2
        assert "trade_count" in res
        assert "winrate" in res
        assert "sharpe_ratio" not in res

def test_extract_trades_df(calculator, sample_data, sample_signals):
    # Test extraction from DataFrame
    with patch("monte_neo.metrics.numba_funcs.extract_trades_fast") as mock_fast:
        mock_fast.return_value = [(0, 1, 100.0, 102.0, 1, 2.0, 0.02)]
        trades = calculator._extract_trades(sample_data, sample_signals)
        assert len(trades) == 1
        assert isinstance(trades[0], TradeResult)

def test_extract_trades_numpy(calculator):
    data = np.random.rand(10, 5) # OHLCV
    signals = np.zeros(10, dtype=np.int32)
    with patch("monte_neo.metrics.calculator.HAS_NATIVE", False):
        with patch("monte_neo.metrics.numba_funcs.extract_trades_fast") as mock_fast:
            mock_fast.return_value = []
            calculator._extract_trades(data, signals)
            assert mock_fast.called

def test_calculate_equity(calculator):
    trades = [
        TradeResult(0, 1, 100.0, 101.0, 1, 1.0, 0.01),
        TradeResult(2, 3, 101.0, 102.01, 1, 1.01, 0.01)
    ]
    calculator.initial_capital = 1000
    equity = calculator._calculate_equity(trades)
    assert len(equity) == 3
    assert equity[0] == 1000
    assert equity[1] == 1010
    assert equity[2] == pytest.approx(1020.1)

def test_calculate_equity_leverage(calculator):
    calculator.leverage = 2.0
    calculator.initial_capital = 1000
    trades = [TradeResult(0, 1, 100.0, 101.0, 1, 1.0, 0.01)]
    equity = calculator._calculate_equity(trades)
    # 1% gain * 2 leverage = 2% gain
    assert equity[1] == 1020

def test_batch_fast_static(calculator):
    with patch("monte_neo.metrics.numba_funcs.calculate_batch_fast") as mock_batch:
        MetricsCalculator.calculate_batch_fast(None, None, None, None, False, 0, 0)
        assert mock_batch.called

def test_batch_multi_price_fast_static(calculator):
    with patch("monte_neo.metrics.numba_funcs.calculate_batch_multi_price_fast") as mock_batch:
        MetricsCalculator.calculate_batch_multi_price_fast(None, None, None, None, False, 0, 0)
        assert mock_batch.called

def test_extract_trades_missing_column(calculator, sample_data):
    signals = pd.DataFrame({"wrong": [1, 2, 3]})
    trades = calculator._extract_trades(sample_data, signals)
    assert trades == []

def test_calculate_equity_empty(calculator):
    equity = calculator._calculate_equity([])
    assert len(equity) == 1
    assert equity[0] == calculator.initial_capital

def test_has_native_type():
    # Just verify HAS_NATIVE is a boolean
    import monte_neo.metrics.calculator as calc_mod
    assert isinstance(calc_mod.HAS_NATIVE, bool)

def test_extract_trades_native_path(calculator, sample_data, sample_signals):
    # Force HAS_NATIVE to True and test the native path
    with patch("monte_neo.metrics.calculator.HAS_NATIVE", True):
        with patch("monte_neo.core.native_metrics.extract_trades") as mock_native:
            mock_native.return_value = []
            calculator._extract_trades(sample_data, sample_signals)
            assert mock_native.called
