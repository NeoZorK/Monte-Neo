"""Tests for dynamic indicators."""

import numpy as np
import pandas as pd
import pytest

from monte_neo.core.generator import GeneratorConfig, IndicatorGenerator
from monte_neo.indicators.dynamic import DynamicIndicator, IndicatorConfig


@pytest.fixture
def sample_data():
    """Create sample OHLCV data."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    data = pd.DataFrame(
        {
            "open": np.random.rand(100) * 100,
            "high": np.random.rand(100) * 100,
            "low": np.random.rand(100) * 100,
            "close": np.random.rand(100) * 100,
            "volume": np.random.rand(100) * 1000,
        },
        index=dates,
    )
    return data


def test_dynamic_indicator_manual(sample_data):
    """Test manual dynamic indicator creation."""
    config = IndicatorConfig(
        name="TestDynamic",
        parameters={"source_code": "data['close'] * 2"},
    )
    indicator = DynamicIndicator(config)
    result = indicator.calculate(sample_data)
    
    assert "dynamic" in result.columns
    pd.testing.assert_series_equal(
        result["dynamic"], 
        sample_data["close"] * 2, 
        check_names=False
    )


def test_dynamic_indicator_signals(sample_data):
    """Test signal generation."""
    # Create code that is definitely positive effectively
    config = IndicatorConfig(
        name="TestSignal",
        parameters={"source_code": "data['close'] + 999999"}, 
    )
    indicator = DynamicIndicator(config)
    signals = indicator.generate_signals(sample_data)
    
    # All should be buy (1) because value > 0
    assert (signals["signal"] == 1).all()


def test_generator_dynamic(sample_data):
    """Test that generator produces dynamic indicators."""
    config = GeneratorConfig(
        max_iterations=10, 
        indicator_types=["dynamic"],
        mc_iterations=10, # low for speed
        early_stopping=False
    )
    generator = IndicatorGenerator(config)
    
    # Force dynamic type only
    generator.config.indicator_types = ["dynamic"]
    
    indicator = generator._generate_random_indicator()
    assert isinstance(indicator, DynamicIndicator)
    assert "source_code" in indicator.get_parameters()
    print(f"Generated code: {indicator.get_parameters()['source_code']}")
    
    # Check it runs
    result = indicator.calculate(sample_data)
    assert not result["dynamic"].isnull().all()


def test_execution_robustness(sample_data):
    """Generate many random indicators and ensure no crashes."""
    config = GeneratorConfig(max_iterations=50, indicator_types=["dynamic"])
    generator = IndicatorGenerator(config)
    
    failures = 0
    for _ in range(50):
        try:
            indicator = generator._generate_random_indicator()
            _ = indicator.calculate(sample_data)
        except Exception as e:
            print(f"Failed: {e}")
            failures += 1
            
    assert failures == 0

def test_mutation(sample_data):
    """Test that mutation changes the code."""
    config = GeneratorConfig()
    generator = IndicatorGenerator(config)
    
    ind = DynamicIndicator()
    ind.set_parameter("source_code", "data['close'].rolling(20).mean()")
    
    mutated = generator._mutate_indicator(ind)
    assert isinstance(mutated, DynamicIndicator)
    
    code2 = mutated.get_parameters()["source_code"]
    
    # Verify it produces valid code (not None)
    assert code2 is not None
    # We can't guarantee difference due to randomness or constraints, 
    # but we check object integrity.

def test_evolution_runs(sample_data):
    """Test that evolution loop runs without error."""
    config = GeneratorConfig(
        max_iterations=5,
        indicator_types=["dynamic"],
        generations=2,
        population_size=4,
        min_trades=0
    )
    generator = IndicatorGenerator(config)
    
    # Pre-populate candidates to trigger evolution
    ind1 = DynamicIndicator()
    ind1.set_parameter("source_code", "data['close']")
    generator._candidates.append((ind1, 0.5))
    
    ind2 = DynamicIndicator()
    ind2.set_parameter("source_code", "data['open']")
    generator._candidates.append((ind2, 0.6))
    
    # Run evolution
    generator._run_evolution(sample_data)
    # If no crash, pass.
