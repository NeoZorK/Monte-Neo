import time
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from monte_neo.core.config import GeneratorConfig
from monte_neo.core.generator_search import run_search


@pytest.fixture
def mock_generator():
    gen = MagicMock()
    gen.config = GeneratorConfig()
    gen.config.max_iterations = 10
    gen.config.population_size = 2
    gen.config.mc_pass_threshold = 0.7
    gen.gpu_engine = MagicMock()
    gen._progress_callback = MagicMock()
    gen._generate_random_indicator.side_effect = lambda: MagicMock(get_id=lambda: "id", name="Mock")
    gen._meets_basic_targets.return_value = True
    gen._candidates = []
    return gen

def test_run_search_basic(mock_generator):
    data = pd.DataFrame({"close": np.random.rand(100)})
    
    # Mock GPU backtest results
    mock_generator.gpu_engine.backtest_batch.return_value = [
        {"metrics": {"total_return": 0.1, "profit_factor": 1.5, "max_drawdown": 0.05, "trade_count": 50}}
        for _ in range(10)
    ]
    
    # Mock _run_mc_validation
    mock_mc_result = MagicMock()
    mock_mc_result.pass_rate = 0.9
    mock_mc_result.step_results = []
    mock_generator._run_mc_validation.return_value = mock_mc_result
    
    with patch("monte_neo.core.generator_search._pre_generate_scenarios", return_value=[]):
        with patch("monte_neo.core.generator_search._run_evolution_phase") as mock_evolve:
            mock_evolve.side_effect = lambda g, d, bi, bmr, bmd: (bi, bmr, bmd)
            
            with patch("monte_neo.core.generator_search.ParallelExecutor"):
                res = run_search(mock_generator, data)
                
                assert res.indicator is not None
                assert res.mc_pass_rate == 0.9
                assert res.iterations_tried == 10

def test_run_search_no_targets_met(mock_generator):
    data = pd.DataFrame({"close": np.random.rand(100)})
    mock_generator._meets_basic_targets.return_value = False
    
    mock_generator.gpu_engine.backtest_batch.return_value = [
        {"metrics": {"total_return": -0.1, "trade_count": 5}}
        for _ in range(10)
    ]
    
    with patch("monte_neo.core.generator_search._pre_generate_scenarios", return_value=[]):
        with patch("monte_neo.core.generator_search._run_evolution_phase") as mock_evolve:
            mock_evolve.side_effect = lambda g, d, bi, bmr, bmd: (bi, bmr, bmd)
            
            with patch("monte_neo.core.generator_search.ParallelExecutor"):
                res = run_search(mock_generator, data)
                # Should return fallback if none meet targets
                assert res.indicator is not None
                assert res.mc_pass_rate == 0.0

def test_run_search_exception_handling(mock_generator):
    data = pd.DataFrame({"close": np.random.rand(100)})
    mock_generator.gpu_engine.backtest_batch.side_effect = Exception("GPU Error")
    
    with patch("monte_neo.core.generator_search._pre_generate_scenarios", return_value=[]):
        with patch("monte_neo.core.generator_search._run_evolution_phase") as mock_evolve:
            mock_evolve.side_effect = lambda g, d, bi, bmr, bmd: (bi, bmr, bmd)
            
            with patch("monte_neo.core.generator_search.ParallelExecutor"):
                res = run_search(mock_generator, data)
                # iterations_tried stays 0 because loop over gpu_results is skipped
                assert res.iterations_tried == 0

def test_pre_generate_scenarios(mock_generator):
    from monte_neo.core.generator_search import _pre_generate_scenarios
    data = pd.DataFrame({"close": np.random.rand(100)})
    
    # Case 1: GPU end-to-end path
    mock_generator.config.use_gpu = True
    mock_generator.config.use_mc_shuffling = True
    mock_generator.config.use_mc_noise = False
    mock_generator.config.use_mc_sensitivity = False
    mock_generator.config.use_mc_walk_forward = False
    mock_generator.config.use_mc_block_bootstrap = False
    assert _pre_generate_scenarios(mock_generator, data, 10) is None
    
    # Case 2: Block bootstrap enabled
    mock_generator.config.use_gpu = False
    mock_generator.config.use_mc_block_bootstrap = True
    assert _pre_generate_scenarios(mock_generator, data, 10) is None
    
    # Case 3: Successful pre-generation
    mock_generator.config.use_mc_block_bootstrap = False
    mock_generator.config.mc_iterations = 10
    with patch("monte_neo.core.generator_search.MonteCarloEngine") as mock_engine:
        mock_instance = mock_engine.return_value
        mock_instance.scenario_builder.generate.return_value = [data]
        res = _pre_generate_scenarios(mock_generator, data, 10)
        assert res == [data]
        
    # Case 4: Exception handling
    with patch("monte_neo.core.generator_search.MonteCarloEngine", side_effect=Exception("MC Error")):
        assert _pre_generate_scenarios(mock_generator, data, 10) is None

def test_update_progress(mock_generator):
    from monte_neo.core.generator_search import _update_progress
    _update_progress(mock_generator, time.time() - 10, 0, 10, 100, 0.5)
    mock_generator._progress_callback.assert_called()

def test_run_search_keyboard_interrupt(mock_generator):
    data = pd.DataFrame({"close": np.random.rand(100)})
    mock_generator.gpu_engine.backtest_batch.side_effect = KeyboardInterrupt()
    
    with patch("monte_neo.core.generator_search._pre_generate_scenarios", return_value=[]):
        res = run_search(mock_generator, data)
        assert res.iterations_tried == 0
        mock_generator._progress_callback.assert_called_with(0, 10, "Interrupted by user")

def test_run_search_shutdown_requested(mock_generator):
    data = pd.DataFrame({"close": np.random.rand(100)})
    mock_generator.gpu_engine.backtest_batch.return_value = [
        {"metrics": {"total_return": 0.1, "trade_count": 50}}
    ]
    # Mock executor shutdown
    mock_executor = MagicMock()
    mock_executor._shutdown_requested = True
    mock_generator.executor = mock_executor
    
    with patch("monte_neo.core.generator_search.ParallelExecutor", return_value=mock_executor):
        res = run_search(mock_generator, data)
        # Should stop after first batch due to shutdown requested
        assert res.iterations_tried == 1
