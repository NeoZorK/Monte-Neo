import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from monte_neo.monte_carlo.workers import (
    init_worker, init_worker_data, _generate_signals_wrapper,
    run_indicator_batch, run_scenario_batch, run_single_scenario,
    run_block_bootstrap_scenario, SHARED_DATA, SHARED_SCENARIOS
)

@pytest.fixture(autouse=True)
def cleanup_globals():
    import monte_neo.monte_carlo.workers as workers
    workers.SHARED_DATA = None
    workers.SHARED_SCENARIOS = None
    yield
    workers.SHARED_DATA = None
    workers.SHARED_SCENARIOS = None

def test_init_worker():
    scenarios = [pd.DataFrame({"close": [1, 2]})]
    init_worker(scenarios)
    import monte_neo.monte_carlo.workers as workers
    assert workers.SHARED_SCENARIOS == scenarios

def test_init_worker_data():
    data = pd.DataFrame({"close": [1, 2]})
    init_worker_data(data)
    import monte_neo.monte_carlo.workers as workers
    assert workers.SHARED_DATA.equals(data)

def test_generate_signals_wrapper_with_df():
    indicator = MagicMock()
    indicator.generate_signals_fast.return_value = np.array([1, 0, 1])
    df = pd.DataFrame({"close": [1, 2, 3]})
    
    res = _generate_signals_wrapper((indicator, df))
    assert np.array_equal(res, [1, 0, 1])
    indicator.generate_signals_fast.assert_called_once_with(df)

def test_generate_signals_wrapper_with_shared():
    indicator = MagicMock()
    indicator.generate_signals_fast.return_value = np.array([1, 0, 1])
    data = pd.DataFrame({"close": [1, 2, 3]})
    init_worker_data(data)
    
    res = _generate_signals_wrapper((indicator, None))
    assert np.array_equal(res, [1, 0, 1])
    indicator.generate_signals_fast.assert_called_once_with(data)

def test_generate_signals_wrapper_no_data():
    indicator = MagicMock()
    res = _generate_signals_wrapper((indicator, None))
    assert len(res) == 0

def test_run_indicator_batch():
    indicator = MagicMock()
    indicator.generate_signals_fast.return_value = np.array([1, 1])
    df = pd.DataFrame({"close": [1, 2]})
    
    res = run_indicator_batch(([indicator], df))
    assert len(res) == 1
    assert np.array_equal(res[0], [1, 1])

def test_run_indicator_batch_error():
    indicator = MagicMock()
    indicator.generate_signals_fast.side_effect = Exception("Error")
    df = pd.DataFrame({"close": [1, 2]})
    
    res = run_indicator_batch(([indicator], df))
    assert len(res) == 1
    assert np.array_equal(res[0], [0, 0])

def test_run_scenario_batch_explicit():
    indicator = MagicMock()
    indicator.generate_signals_fast.return_value = np.array([1, 1])
    metrics_calc = MagicMock()
    metrics_calc.calculate_all.return_value = {"winrate": 0.6}
    
    df = pd.DataFrame({"close": [1, 2]})
    target_metrics = {"winrate": 0.5}
    
    results = run_scenario_batch([df], indicator, metrics_calc, target_metrics)
    assert len(results) == 1
    assert results[0][0] is True
    assert results[0][1] == {"winrate": 0.6}

def test_run_scenario_batch_shared():
    indicator = MagicMock()
    indicator.generate_signals_fast.return_value = np.array([1, 1])
    metrics_calc = MagicMock()
    metrics_calc.calculate_all.return_value = {"winrate": 0.4}
    
    df = pd.DataFrame({"close": [1, 2]})
    init_worker([df])
    target_metrics = {"winrate": 0.5}
    
    results = run_scenario_batch(None, indicator, metrics_calc, target_metrics, indices=[0])
    assert len(results) == 1
    assert results[0][0] is False # winrate 0.4 < 0.5

def test_run_single_scenario():
    indicator = MagicMock()
    indicator.generate_signals_fast.return_value = np.array([1])
    metrics_calc = MagicMock()
    metrics_calc.calculate_all.return_value = {"max_drawdown": 0.05}
    
    df = pd.DataFrame({"close": [1]})
    target_metrics = {"max_drawdown": 0.1}
    
    passed, metrics = run_single_scenario(df, indicator, metrics_calc, target_metrics)
    assert passed is True
    assert metrics == {"max_drawdown": 0.05}

def test_run_block_bootstrap_scenario():
    data = pd.DataFrame({"close": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 
                         "open": [1]*10, "high": [1]*10, "low": [1]*10})
    init_worker_data(data)
    
    indicator = MagicMock()
    indicator.generate_signals_fast.return_value = np.zeros(10)
    
    res = run_block_bootstrap_scenario(indicator, seed=42, block_size=2)
    assert res is not None
    signals, returns, ohlc = res
    assert len(signals) == 10
    assert len(returns) == 9
    assert ohlc.shape == (10, 4)
