from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from monte_neo.core.config import GeneratorConfig
from monte_neo.core.generator import IndicatorGenerator
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.indicators.technical import MACDIndicator, RSIIndicator, SMAIndicator


@pytest.fixture
def generator():
    config = GeneratorConfig()
    with patch("monte_neo.core.gpu_engine.MLXBacktestEngine"):
        return IndicatorGenerator(config)

@pytest.fixture
def sample_data():
    return pd.DataFrame({
        "open": np.random.rand(100),
        "high": np.random.rand(100),
        "low": np.random.rand(100),
        "close": np.random.rand(100),
        "volume": np.random.rand(100)
    })

def test_init(generator):
    assert generator.config is not None
    assert generator.metrics_calc is not None
    assert generator.gpu_engine is not None

def test_set_progress_callback(generator):
    callback = MagicMock()
    generator.set_progress_callback(callback)
    assert generator._progress_callback == callback

def test_run_mc_validation(generator, sample_data):
    indicator = SMAIndicator()
    with patch("monte_neo.core.generator.MonteCarloEngine") as mock_engine_cls:
        mock_engine = mock_engine_cls.return_value
        mock_engine.run.return_value = MagicMock()
        
        res = generator._run_mc_validation(sample_data, indicator)
        assert mock_engine_cls.called
        assert mock_engine.run.called

def test_generate_random_indicator(generator):
    # Test multiple generations to cover different types
    generator.config.indicator_types = ["sma", "rsi", "macd", "dynamic"]
    for _ in range(20):
        ind = generator._generate_random_indicator()
        assert isinstance(ind, (SMAIndicator, RSIIndicator, MACDIndicator, DynamicIndicator))

def test_generate_random_indicator_fallback(generator):
    # Test fallback to SMA for unknown indicator type
    generator.config.indicator_types = ["unknown"]
    ind = generator._generate_random_indicator()
    assert isinstance(ind, SMAIndicator)

def test_meets_basic_targets(generator):
    generator.config.target_metrics = {"winrate": 0.5, "max_drawdown": 0.1, "consecutive_losses": 5}
    
    # Passes
    assert generator._meets_basic_targets({"winrate": 0.6, "max_drawdown": 0.05, "consecutive_losses": 3}) is True
    # Fails winrate
    assert generator._meets_basic_targets({"winrate": 0.4, "max_drawdown": 0.05}) is False
    # Fails drawdown
    assert generator._meets_basic_targets({"winrate": 0.6, "max_drawdown": 0.15}) is False
    # Fails consecutive losses
    assert generator._meets_basic_targets({"winrate": 0.6, "max_drawdown": 0.05, "consecutive_losses": 10}) is False
    # Missing metric (ignored)
    assert generator._meets_basic_targets({"winrate": 0.6}) is True

def test_run_evolution_default_population(generator, sample_data):
    # Test _run_evolution with default population from _candidates
    indicator = SMAIndicator()
    generator._candidates = [(indicator, 0.5)]
    with patch("monte_neo.core.generator.EvolutionEngine") as mock_evo_cls:
        mock_evo = mock_evo_cls.return_value
        mock_evo.run.return_value = indicator
        
        res = generator._run_evolution(sample_data)
        assert res == indicator
        assert mock_evo_cls.called

def test_mutate_indicator(generator):
    indicator = SMAIndicator()
    with patch("monte_neo.core.generator.EvolutionEngine") as mock_evo_cls:
        mock_evo = mock_evo_cls.return_value
        mock_evo._mutate_indicator.return_value = indicator
        
        res = generator._mutate_indicator(indicator)
        assert res == indicator
        assert mock_evo_cls.called

def test_run_evolution(generator, sample_data):
    population = [SMAIndicator(), RSIIndicator()]
    with patch("monte_neo.core.generator.EvolutionEngine") as mock_evo_cls:
        mock_evo = mock_evo_cls.return_value
        mock_evo.run.return_value = population[0]
        
        res = generator._run_evolution(sample_data, population)
        assert res == population[0]
        assert mock_evo_cls.called

def test_estimate_time(generator, sample_data):
    with patch("monte_neo.core.generator.estimate_time") as mock_est:
        mock_est.return_value = 5.0
        assert generator.estimate_time(sample_data) == 5.0
        mock_est.assert_called_once_with(generator, sample_data)

def test_generate(generator, sample_data):
    with patch("monte_neo.core.generator.run_search") as mock_search:
        mock_search.return_value = MagicMock()
        generator.generate(sample_data)
        mock_search.assert_called_once_with(generator, sample_data)
