"""Unit tests for Monte Carlo simulation methods."""

import pytest
import pandas as pd
import numpy as np
from monte_neo.monte_carlo.shuffler import DataShuffler
from monte_neo.monte_carlo.noise import NoiseInjector
from monte_neo.monte_carlo.sensitivity import SensitivityAnalyzer
from monte_neo.monte_carlo.walk_forward import WalkForwardAnalyzer

def test_data_shuffler(sample_ohlcv):
    shuffler = DataShuffler(random_seed=42)
    
    # Shuffle returns
    shuffled_list = shuffler.shuffle_returns(sample_ohlcv, n_samples=1)
    assert len(shuffled_list) == 1
    assert not shuffled_list[0]["close"].equals(sample_ohlcv["close"])
    
    # Block shuffle
    blocked_list = shuffler.shuffle_blocks(sample_ohlcv, n_samples=1, block_size=10)
    assert len(blocked_list) == 1
    
    # Session shuffle (if we add 'session' index or simulate it)
    session_list = shuffler.shuffle_within_session(sample_ohlcv, n_samples=1)
    assert len(session_list) == 1
    
    # Column shuffle
    column_list = shuffler.shuffle_columns(sample_ohlcv, n_samples=1, columns=["volume"])
    assert len(column_list) == 1

def test_noise_injector(sample_ohlcv):
    gen = NoiseInjector(random_seed=42)
    
    # Simple noise
    noisy_list = gen.add_noise(sample_ohlcv, n_samples=1, noise_level=0.01)
    assert len(noisy_list) == 1
    
    # Slippage simulation
    with_slippage = gen.add_slippage(sample_ohlcv, slippage_bps=10)
    assert len(with_slippage) == len(sample_ohlcv)
    
    # Other noise types
    with_spread = gen.add_spread_variation(sample_ohlcv, n_samples=1, base_spread_bps=5)
    assert len(with_spread) == 1
    
    with_volume = gen.add_volume_noise(sample_ohlcv, n_samples=1, noise_level=0.1)
    assert len(with_volume) == 1

def test_sensitivity_analyzer(sample_ohlcv):
    from monte_neo.indicators.technical import SMAIndicator
    from monte_neo.metrics.calculator import MetricsCalculator
    
    analyzer = SensitivityAnalyzer()
    indicator = SMAIndicator()
    metrics_calc = MetricsCalculator()
    
    # Needs some data to run
    results = analyzer.analyze_parameter(
        indicator=indicator,
        param_name="fast_period",
        base_value=12,
        data=sample_ohlcv,
        metrics_calc=metrics_calc
    )
    
    assert hasattr(results, "stability_score")
    assert results.stability_score >= 0

def test_walk_forward(sample_ohlcv):
    from monte_neo.indicators.technical import SMAIndicator
    from monte_neo.metrics.calculator import MetricsCalculator
    
    wf = WalkForwardAnalyzer(n_splits=3, train_pct=0.7)
    indicator = SMAIndicator()
    metrics_calc = MetricsCalculator()
    target_metrics = {"profit_factor": 1.1}
    
    # Test split logic
    windows = wf._generate_windows(len(sample_ohlcv))
    assert len(windows) <= 3
    
    # Test analyze logic
    result = wf.analyze(indicator, sample_ohlcv, metrics_calc, target_metrics)
    assert hasattr(result, "overall_passed")
    assert len(result.windows) > 0
    assert "profit_factor" in result.avg_test_performance
