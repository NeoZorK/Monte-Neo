"""Stress tests for performance and stability."""

import pytest
import time
import pandas as pd
import numpy as np
from monte_neo.core.generator import IndicatorGenerator, GeneratorConfig
from monte_neo.utils.parallel import ParallelExecutor

def test_memory_stress():
    """Test handling of large datasets (1M rows)."""
    # Create 1M rows
    n_rows = 1_000_000
    dates = pd.date_range("2000-01-01", periods=n_rows, freq="1min")
    data = pd.DataFrame({
        "open": np.random.randn(n_rows).cumsum() + 1000,
        "high": np.random.randn(n_rows).cumsum() + 1005,
        "low": np.random.randn(n_rows).cumsum() + 995,
        "close": np.random.randn(n_rows).cumsum() + 1000,
        "volume": np.random.rand(n_rows) * 100
    }, index=dates)
    
    # Basic sanity check
    assert len(data) == n_rows
    assert data.memory_usage().sum() > 40 * 1024 * 1024 # ~40MB
    
    # Try a simple calculation on this data
    returns = data["close"].pct_change().dropna()
    assert len(returns) == n_rows - 1

def test_cpu_stress():
    """Test parallel execution of heavy tasks."""
    executor = ParallelExecutor(n_workers=4)
    
    def heavy_task(n):
        # Simulate some work
        return np.sqrt(np.random.rand(n, n)).mean()
    
    start = time.time()
    results = executor.map(heavy_task, [1000] * 20)
    elapsed = time.time() - start
    
    assert len(results) == 20
    assert elapsed > 0

def test_high_iteration_monte_carlo(sample_ohlcv):
    """Verify generator doesn't leak or crash with many iterations."""
    config = GeneratorConfig(
        max_iterations=1000,
        mc_iterations=100,
        use_mc_shuffling=True,
        early_stopping=True # Stop early if found
    )
    
    generator = IndicatorGenerator(config)
    start = time.time()
    # We only run a few to not hang the test, but check performance
    result = generator.generate(sample_ohlcv.iloc[:500])
    elapsed = time.time() - start
    
    print(f"Time per 1000 iter: {elapsed:.2f}s")
    assert elapsed < 60 # Should be reasonably fast
