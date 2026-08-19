from unittest.mock import MagicMock, patch

import numpy as np

from monte_neo.core.gpu_lazy import backtest_lazy_scenarios


def test_backtest_lazy_scenarios_no_sl_tp():
    indicator = MagicMock()
    executor = MagicMock()
    
    # Mock return: (sigs, rets, ohlc)
    mock_raw_results = [
        (np.ones(11), np.ones(10), np.ones((11, 4))),
        (np.ones(11), np.ones(10), np.ones((11, 4)))
    ]
    executor.map.return_value = mock_raw_results
    
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
        
        results = backtest_lazy_scenarios(indicator, n_scenarios=2, executor=executor, use_sl_tp=False)
        
        assert len(results) == 2
        assert "total_return" in results[0]
        assert "metrics" in results[0]

def test_backtest_lazy_scenarios_with_sl_tp():
    indicator = MagicMock()
    executor = MagicMock()
    
    # Mock return: (sigs, rets, ohlc)
    # ohlc is [open, high, low, close]
    mock_raw_results = [
        (np.ones(10), np.ones(9), np.ones((10, 4))),
        (np.ones(10), np.ones(9), np.ones((10, 4)))
    ]
    executor.map.return_value = mock_raw_results
    
    mock_batch_metrics = np.array([
        [0.1, 0.05, 1.5, 5],
        [0.2, 0.1, 2.0, 10]
    ])
    
    with patch("monte_neo.metrics.calculator.MetricsCalculator.calculate_batch_multi_price_fast", return_value=mock_batch_metrics):
        
        results = backtest_lazy_scenarios(indicator, n_scenarios=2, executor=executor, use_sl_tp=True)
        
        assert len(results) == 2
        assert results[0]["total_return"] == 0.1
        assert results[1]["total_return"] == 0.2
        assert results[0]["metrics"]["trade_count"] == 5

def test_backtest_lazy_scenarios_empty():
    indicator = MagicMock()
    executor = MagicMock()
    executor.map.return_value = [None, None]
    
    results = backtest_lazy_scenarios(indicator, n_scenarios=2, executor=executor)
    assert results == []
