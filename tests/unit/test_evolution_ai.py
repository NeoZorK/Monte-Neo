import numpy as np
import pandas as pd
import pytest

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
    engine = AIEvolutionEngine(population_size=10)
    assert engine.population_size == 10
    assert engine.mutation_rate == 0.2

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
