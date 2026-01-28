import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from monte_neo.core.gpu_scenarios import normalize_signal_array, run_scenarios_backtest

def test_normalize_signal_array():
    # Test case 1: Empty target length
    assert len(normalize_signal_array(np.array([1, 1]), 0)) == 0
    
    # Test case 2: None signals
    res = normalize_signal_array(None, 5)
    assert len(res) == 5
    assert np.all(res == 0)
    
    # Test case 3: DataFrame input
    df = pd.DataFrame({"signal": [1, -1, 0]})
    res = normalize_signal_array(df, 3)
    assert np.array_equal(res, [1, -1, 0])
    
    # Test case 4: Padding
    res = normalize_signal_array(np.array([1, 1]), 5)
    assert np.array_equal(res, [1, 1, 0, 0, 0])
    
    # Test case 5: Truncating
    res = normalize_signal_array(np.array([1, 1, 1, 1, 1]), 2)
    assert np.array_equal(res, [1, 1])

def test_run_scenarios_backtest_no_sl_tp():
    indicator = MagicMock()
    indicator.generate_signals.return_value = np.ones(10)
    
    scenarios = [
        pd.DataFrame({"close": np.ones(11)}),
        pd.DataFrame({"close": np.ones(11)})
    ]
    
    mock_rets = np.ones((2, 10))
    mock_stats = np.array([1.0, 1.0])
    
    with patch("mlx.core.array") as mock_array, \
         patch("mlx.core.exp", return_value=mock_rets), \
         patch("mlx.core.cumsum", return_value=mock_rets), \
         patch("mlx.core.log1p", return_value=mock_rets), \
         patch("mlx.core.clip", return_value=mock_rets), \
         patch("mlx.core.cummax", return_value=mock_rets), \
         patch("mlx.core.max", return_value=mock_stats), \
         patch("mlx.core.sum", return_value=mock_stats), \
         patch("mlx.core.where", return_value=mock_stats), \
         patch("mlx.core.abs", return_value=mock_stats):
        
        mock_array.return_value = mock_rets
        
        results = run_scenarios_backtest(indicator, scenarios, use_sl_tp=False)
        
        assert len(results) == 2
        assert "total_return" in results[0]
        assert "metrics" in results[0]

def test_run_scenarios_backtest_with_sl_tp():
    indicator = MagicMock()
    scenarios = [
        pd.DataFrame({"close": np.ones(10), "high": np.ones(10), "low": np.ones(10)}),
        pd.DataFrame({"close": np.ones(10), "high": np.ones(10), "low": np.ones(10)})
    ]
    
    mock_batch_metrics = np.array([
        [0.1, 0.05, 1.5, 5],
        [0.2, 0.1, 2.0, 10]
    ])
    
    with patch("monte_neo.metrics.calculator.MetricsCalculator.calculate_batch_multi_price_fast", return_value=mock_batch_metrics), \
         patch("monte_neo.utils.parallel.ParallelExecutor.map", return_value=[np.ones(10), np.ones(10)]):
        
        results = run_scenarios_backtest(indicator, scenarios, use_sl_tp=True)
        
        assert len(results) == 2
        assert results[0]["total_return"] == 0.1
        assert results[1]["total_return"] == 0.2
        assert results[0]["metrics"]["trade_count"] == 5
