import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from monte_neo.core.generator_utils import estimate_time, PARAM_SPACES
from monte_neo.core.generator_worker import _search_worker
from monte_neo.indicators.base import BaseIndicator

class MockIndicator(BaseIndicator):
    def calculate(self, data):
        return np.zeros(len(data))
    def generate_signals(self, data):
        return np.zeros(len(data))
    def generate_signals_fast(self, data):
        return np.zeros(len(data))

def test_param_spaces():
    assert "sma" in PARAM_SPACES
    assert "rsi" in PARAM_SPACES
    assert "macd" in PARAM_SPACES
    assert "dynamic" in PARAM_SPACES

def test_estimate_time():
    generator = MagicMock()
    generator.config.use_mc_shuffling = False
    generator.config.use_mc_noise = False
    generator.config.max_iterations = 100
    generator.metrics_calc = MagicMock()
    generator.metrics_calc.calculate_all.return_value = {"total_profit": 0.1}
    
    indicator = MockIndicator()
    generator._generate_random_indicator.return_value = indicator
    
    data = pd.DataFrame({"close": np.random.rand(100)})
    
    est = estimate_time(generator, data)
    assert isinstance(est, float)
    assert est >= 0

def test_search_worker_low_trades():
    indicator = MockIndicator()
    data = pd.DataFrame({"close": np.random.rand(100)})
    metrics_calc = MagicMock()
    metrics_calc.calculate_all.return_value = {"trade_count": 5} # Less than min_trades
    
    args = (
        indicator, data, metrics_calc, {}, 10, False, False, False, False, 10, False, 0.0, 0.0
    )
    
    res_ind, res_rate = _search_worker(args)
    assert res_ind is None
    assert res_rate == 0.0

def test_search_worker_failed_targets():
    indicator = MockIndicator()
    data = pd.DataFrame({"close": np.random.rand(100)})
    metrics_calc = MagicMock()
    metrics_calc.calculate_all.return_value = {"trade_count": 20, "winrate": 0.3}
    
    target_metrics = {"winrate": 0.5} # Target 0.5 > Actual 0.3
    
    args = (
        indicator, data, metrics_calc, target_metrics, 10, False, False, False, False, 10, False, 0.0, 0.0
    )
    
    res_ind, res_rate = _search_worker(args)
    assert res_ind is None
    assert res_rate == 0.0

def test_search_worker_success():
    indicator = MockIndicator()
    data = pd.DataFrame({"close": np.random.rand(100)})
    metrics_calc = MagicMock()
    metrics_calc.calculate_all.return_value = {"trade_count": 20, "winrate": 0.6}
    
    target_metrics = {"winrate": 0.5}
    
    with patch("monte_neo.monte_carlo.engine.MonteCarloEngine") as mock_engine:
        mock_instance = mock_engine.return_value
        mock_instance.run.return_value = MagicMock(pass_rate=0.8)
        
        args = (
            indicator, data, metrics_calc, target_metrics, 10, False, False, False, False, 10, False, 0.0, 0.0
        )
        
        res_ind, res_rate = _search_worker(args)
        assert res_ind == indicator
        assert res_rate == 0.8
