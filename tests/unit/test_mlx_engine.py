from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from monte_neo.core.mlx_engine import MLXBacktestEngine


@pytest.fixture
def mock_mx():
    with patch("mlx.core") as mx:
        yield mx

@pytest.fixture
def engine():
    with patch("monte_neo.core.mlx_engine.GpuAccelerationEngine"):
        return MLXBacktestEngine()

@pytest.fixture
def sample_data():
    return pd.DataFrame({
        "open": [100.0] * 10,
        "high": [101.0] * 10,
        "low": [99.0] * 10,
        "close": [100.0] * 10,
        "volume": [1000.0] * 10
    })

def test_engine_init():
    with patch("monte_neo.core.mlx_engine.GpuAccelerationEngine") as mock_gpu:
        engine = MLXBacktestEngine(precision="float16", metal_driver="cpp")
        assert engine.precision == "float16"
        assert engine.metal_driver == "cpp"
        assert mock_gpu.called

def test_run_full_simulation_native(engine, sample_data):
    indicator = MagicMock()
    indicator.to_mlx_representation.return_value = MagicMock()
    indicator.get_metal_params.return_value = [1.0, 2.0]
    
    engine.native_bridge = MagicMock()
    engine.native_bridge.run_backtest.return_value = [MagicMock(total_return=0.1, trade_count=5, profit_factor=1.5, win_rate=0.6, max_drawdown=0.05, sharpe_ratio=1.0)]
    
    results, stats = engine.run_full_simulation(sample_data, indicator, n_scenarios=1, method="shuffling")
    assert len(results) == 1
    assert results[0]["metrics"]["total_return"] == 0.1
    assert "kernel_execution" in stats

def test_run_full_simulation_mlx_sl_tp(engine, sample_data):
    indicator = MagicMock()
    indicator.to_mlx_representation.return_value = MagicMock()
    indicator.get_metal_params.return_value = None # Force fallback
    
    with patch("monte_neo.core.acceleration.tensor_ops.to_tensor") as mock_to_tensor:
        mock_to_tensor.return_value = {"close": np.zeros(10)}
        with patch("monte_neo.core.acceleration.tensor_ops.TensorOps.generate_shuffle_scenarios") as mock_gen:
            # Return a 2D array
            mock_gen.return_value = np.zeros((1, 10))
            with patch("monte_neo.metrics.calculator.MetricsCalculator.calculate_batch_multi_price_fast") as mock_batch:
                mock_batch.return_value = np.array([[0.1, 0.05, 1.5, 5]])
                
                results, stats = engine.run_full_simulation(sample_data, indicator, n_scenarios=1, use_sl_tp=True)
                assert len(results) == 1
                assert results[0]["metrics"]["total_return"] == 0.1

def test_run_full_simulation_positional_args(engine, sample_data):
    indicator = MagicMock()
    indicator.to_mlx_representation.return_value = MagicMock()
    indicator.get_metal_params.return_value = None
    
    # Verify it accepts 3 positional arguments: data, indicator_or_list, n_scenarios
    with patch("monte_neo.core.mlx_sim_engine.run_full_simulation_impl") as mock_impl:
        mock_impl.return_value = ([], {})
        engine.run_full_simulation(sample_data, indicator, 10)
        mock_impl.assert_called_once_with(engine, sample_data, indicator, 10)

def test_backtest_population_multi_scenario_dispatch(engine, sample_data):
    population = [MagicMock(), MagicMock()]
    n_scenarios = 5
    
    with patch("monte_neo.core.mlx_3d_engine.backtest_population_multi_scenario_impl") as mock_impl:
        mock_impl.return_value = np.zeros((2, 5, 6))
        results = engine.backtest_population_multi_scenario(data=sample_data, population=population, n_scenarios=n_scenarios)
        assert results.shape == (2, 5, 6)
        mock_impl.assert_called_once()

def test_backtest_batch_sequential(engine, sample_data):
    indicator = MagicMock()
    indicator.generate_signals_fast.return_value = np.zeros(10)
    
    mock_close = np.ones(10)
    mock_signals = np.ones((1, 10))
    mock_equity = np.ones((1, 9))
    # Things that should be (n_indicators,)
    mock_stats = np.array([1.0])
    
    with patch("mlx.core.array") as mock_mx_array, \
         patch("mlx.core.exp", return_value=mock_equity), \
         patch("mlx.core.cumsum", return_value=mock_equity), \
         patch("mlx.core.log1p", return_value=mock_equity), \
         patch("mlx.core.clip", return_value=mock_equity), \
         patch("mlx.core.cummax", return_value=mock_equity), \
         patch("mlx.core.max", return_value=mock_stats), \
         patch("mlx.core.sum", return_value=mock_stats), \
         patch("mlx.core.where") as mock_mx_where, \
         patch("mlx.core.abs", return_value=mock_stats), \
         patch("mlx.core.log", return_value=mock_equity):
            
            def array_side_effect(obj, *args, **kwargs):
                if isinstance(obj, np.ndarray) and obj.ndim == 1:
                    return mock_close
                return mock_signals
            
            def where_side_effect(condition, x, y):
                # If x is 2D (like strat_returns), return 2D
                if hasattr(x, "ndim") and x.ndim == 2:
                    return mock_equity
                if isinstance(x, np.ndarray) and x.ndim == 2:
                    return mock_equity
                # Otherwise return 1D stats
                return mock_stats

            mock_mx_array.side_effect = array_side_effect
            mock_mx_where.side_effect = where_side_effect
            
            results = engine.backtest_batch(data=sample_data, indicators=[indicator])
            assert len(results) == 1
            assert "metrics" in results[0]

def test_backtest_batch_parallel(engine, sample_data):
    indicator = MagicMock()
    executor = MagicMock()
    executor.use_processes = True
    executor.n_workers = 4
    executor.map.return_value = [[np.zeros(10)]]
    
    mock_close = np.ones(10)
    mock_signals = np.ones((1, 10))
    mock_equity = np.ones((1, 9))
    mock_stats = np.array([1.0])
    
    with patch("mlx.core.array") as mock_mx_array, \
         patch("mlx.core.exp", return_value=mock_equity), \
         patch("mlx.core.cumsum", return_value=mock_equity), \
         patch("mlx.core.log1p", return_value=mock_equity), \
         patch("mlx.core.clip", return_value=mock_equity), \
         patch("mlx.core.cummax", return_value=mock_equity), \
         patch("mlx.core.max", return_value=mock_stats), \
         patch("mlx.core.sum", return_value=mock_stats), \
         patch("mlx.core.where") as mock_mx_where, \
         patch("mlx.core.abs", return_value=mock_stats), \
         patch("mlx.core.log", return_value=mock_equity):
            
            def array_side_effect(obj, *args, **kwargs):
                if isinstance(obj, np.ndarray) and obj.ndim == 1:
                    return mock_close
                return mock_signals
            
            def where_side_effect(condition, x, y):
                if hasattr(x, "ndim") and x.ndim == 2:
                    return mock_equity
                if isinstance(x, np.ndarray) and x.ndim == 2:
                    return mock_equity
                return mock_stats

            mock_mx_array.side_effect = array_side_effect
            mock_mx_where.side_effect = where_side_effect
            
            results = engine.backtest_batch(data=sample_data, indicators=[indicator], executor=executor, force_parallel=True)
            assert executor.map.called
            assert len(results) == 1

