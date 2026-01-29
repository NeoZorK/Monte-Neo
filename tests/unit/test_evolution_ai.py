import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from monte_neo.core.evolution_ai import AIEvolutionEngine
from monte_neo.indicators.dynamic import DynamicIndicator


@pytest.fixture
def sample_data():
    dates = pd.date_range("2023-01-01", periods=100)
    data = pd.DataFrame({
        "open": np.random.randn(100).cumsum() + 100,
        "high": np.random.randn(100).cumsum() + 105,
        "low": np.random.randn(100).cumsum() + 95,
        "close": np.random.randn(100).cumsum() + 100,
        "volume": np.random.rand(100) * 1000
    }, index=dates)
    return data

def test_engine_init():
    engine = AIEvolutionEngine(population_size=10, use_gpu=False)
    assert engine.population_size == 10
    assert engine.mutation_rate == 0.2
    assert engine.use_gpu is False

def test_evaluate_population_gpu_toggle(sample_data):
    # Test that it calls fallback when use_gpu is False
    engine = AIEvolutionEngine(population_size=2, use_gpu=False)
    pop = engine._initialize_population()
    
    with patch.object(engine, "_fallback_evaluate", return_value=[1.0, 1.0]) as mock_fallback:
        scores = engine._evaluate_population(pop, sample_data, {})
        assert scores == [1.0, 1.0]
        mock_fallback.assert_called_once()

def test_fitness_calculation_improved(sample_data):
    engine = AIEvolutionEngine()
    # Mock results that should give a good score
    # Layout: 0:ret, 1:trades, 2:winrate, 3:maxdd, 4:pf, 5:sharpe
    mock_results = np.array([
        [0.1, 20, 0.6, 0.05, 2.0, 1.0], # Good: ret=0.1, trades=20, dd=0.05, pf=2.0
    ])
    
    with patch.object(engine.mlx_engine, "backtest_population_multi_scenario", return_value=np.array([mock_results])):
        pop = [DynamicIndicator()]
        scores = engine._evaluate_population(pop, sample_data, {})
        # Base score = 3.9, activity bonus = 20 * 0.001 = 0.02
        assert scores[0] == pytest.approx(3.92)

def test_fitness_penalty_low_trades(sample_data):
    engine = AIEvolutionEngine()
    # Mock results with low trades
    mock_results = np.array([
        [0.1, 5, 0.6, 0.05, 2.0, 1.0], # Low trades: 5 < 15
    ])
    
    with patch.object(engine.mlx_engine, "backtest_population_multi_scenario", return_value=np.array([mock_results])):
        pop = [DynamicIndicator()]
        scores = engine._evaluate_population(pop, sample_data, {})
        # Base score = 3.9, penalty = 5/15 = 1/3 -> 1.3
        # Activity bonus = 5 * 0.001 = 0.005
        assert scores[0] == pytest.approx(1.305)


def test_initialize_population():
    engine = AIEvolutionEngine(population_size=5)
    pop = engine._initialize_population()
    assert len(pop) == 5
    assert isinstance(pop[0], DynamicIndicator)

def test_evaluate_population(sample_data):
    engine = AIEvolutionEngine(population_size=3)
    pop = engine._initialize_population()
    targets = {"profit_factor": 2.0, "sharpe_ratio": 1.5}
    scores = engine._evaluate_population(pop, sample_data, targets)
    assert len(scores) == 3
    assert all(s >= 0 for s in scores)

def test_mutate():
    engine = AIEvolutionEngine()
    ind = DynamicIndicator()
    ind.set_parameter("source_code", "close > open")
    mutated = engine._mutate(ind)
    assert isinstance(mutated, DynamicIndicator)
    assert mutated.get_formula() != ""

def test_crossover():
    engine = AIEvolutionEngine()
    p1 = DynamicIndicator()
    p1.set_parameter("source_code", "close > open")
    p2 = DynamicIndicator()
    p2.set_parameter("source_code", "rsi(14) > 50")
    child = engine._crossover(p1, p2)
    assert isinstance(child, DynamicIndicator)
    assert child.get_formula() != ""

def test_evolve_short_run(sample_data):
    engine = AIEvolutionEngine(population_size=4)
    targets = {"profit_factor": 1.5}
    best = engine.evolve(sample_data, targets, generations=2)
    assert isinstance(best, DynamicIndicator)
    assert best.get_formula() != ""
