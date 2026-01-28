import time
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from monte_neo.monte_carlo.engine import MonteCarloEngine
from monte_neo.monte_carlo.types import MCConfig, MCResult


@pytest.fixture
def mock_indicator():
    ind = MagicMock()
    ind.to_mlx_representation.return_value = None
    ind.get_metal_params.return_value = None
    return ind

@pytest.fixture
def mock_metrics_calc():
    return MagicMock()

@pytest.fixture
def engine():
    config = MCConfig(iterations=10, pass_threshold=0.7)
    with patch("monte_neo.core.gpu_engine.MLXBacktestEngine"):
        return MonteCarloEngine(config)

def test_engine_init(engine):
    assert engine.config.iterations == 10
    assert engine.gpu_engine is not None

def test_set_progress_callback(engine):
    callback = MagicMock()
    engine.set_progress_callback(callback)
    assert engine._progress_callback == callback

def test_run_sequential(engine, mock_indicator, mock_metrics_calc):
    engine.config.use_sequential = True
    data = pd.DataFrame({"close": [1, 2]})
    
    with patch("monte_neo.monte_carlo.sequential.SequentialMCRunner") as mock_runner_cls:
        mock_runner = mock_runner_cls.return_value
        mock_runner.run.return_value = MCResult(True, 0.8, 10, 0.1, {}, [])
        
        res = engine.run(data, mock_indicator, mock_metrics_calc, {"winrate": 0.5})
        assert res.passed is True
        assert res.pass_rate == 0.8

def test_run_gpu_full_simulation(engine, mock_indicator, mock_metrics_calc):
    # Setup for pure GPU shuffling
    mock_indicator.to_mlx_representation.return_value = "mlx_rep"
    engine.config.use_shuffling = True
    engine.config.use_noise = False
    engine.config.use_sensitivity = False
    engine.config.use_walk_forward = False
    engine.config.use_block_bootstrap = False
    engine.config.iterations = 200 # > 100
    
    data = pd.DataFrame({"close": np.random.rand(10)})
    engine.gpu_engine.run_full_simulation.return_value = (
        [{"metrics": {"winrate": 0.8}} for _ in range(200)],
        {"total_time": 0.01}
    )
    
    res = engine.run(data, mock_indicator, mock_metrics_calc, {"winrate": 0.5})
    assert res.iterations_run == 200
    assert res.pass_rate == 1.0
    assert res.timing_stats == {"total_time": 0.01}

def test_run_lazy_block_bootstrap(engine, mock_indicator, mock_metrics_calc):
    engine.config.use_block_bootstrap = True
    engine.config.use_shuffling = False
    engine.config.use_noise = False
    engine.config.use_sensitivity = False
    engine.config.use_walk_forward = False
    
    data = pd.DataFrame({"close": np.random.rand(10)})
    engine.gpu_engine.backtest_lazy_scenarios.return_value = [
        {"metrics": {"winrate": 0.6}} for _ in range(10)
    ]
    
    with patch("monte_neo.monte_carlo.engine.ParallelExecutor") as mock_executor:
        res = engine.run(data, mock_indicator, mock_metrics_calc, {"winrate": 0.5})
        assert res.iterations_run == 10
        assert res.pass_rate == 1.0

def test_run_standard_with_gpu_offload(engine, mock_indicator, mock_metrics_calc):
    # Standard mode with > 10 scenarios triggers GPU offload
    engine.config.iterations = 20
    data = pd.DataFrame({"close": np.random.rand(10)})
    
    # Mock scenario generation
    scenarios = [data] * 20
    engine.scenario_builder.generate = MagicMock(return_value=scenarios)
    
    engine.gpu_engine.backtest_scenarios.return_value = [
        {"metrics": {"winrate": 0.4}} for _ in range(20)
    ]
    
    res = engine.run(data, mock_indicator, mock_metrics_calc, {"winrate": 0.5})
    assert res.iterations_run == 20
    assert res.pass_rate == 0.0

def test_run_cpu_fallback(engine, mock_indicator, mock_metrics_calc):
    engine.config.iterations = 5
    data = pd.DataFrame({"close": np.random.rand(10)})
    scenarios = [data] * 5
    engine.scenario_builder.generate = MagicMock(return_value=scenarios)
    
    # Mock CPU parallel execution
    with patch.object(engine, "_run_cpu_parallel") as mock_cpu:
        mock_cpu.return_value = {
            "passed_count": 3,
            "all_results": [{"scenario_idx": i, "passed": i < 3, "metrics": {}} for i in range(5)]
        }
        res = engine.run(data, mock_indicator, mock_metrics_calc, {})
        assert res.iterations_run == 5
        assert res.pass_rate == 0.6

def test_finalize_results(engine):
    all_results = [
        {"scenario_idx": 0, "passed": True, "metrics": {"return": 0.1}},
        {"scenario_idx": 1, "passed": False, "metrics": {"return": -0.05}}
    ]
    with patch("monte_neo.monte_carlo.engine.summarize_metrics") as mock_summ:
        mock_summ.return_value = {"avg_return": 0.025}
        res = engine._finalize_results(1, 2, all_results, time.time() - 1)
        assert res.passed is False # 0.5 < 0.7
        assert res.pass_rate == 0.5
        assert res.iterations_run == 2
        assert res.metrics_summary == {"avg_return": 0.025}
