"""Tests for High-Performance GPU Core (MLX)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

try:
    import mlx.core as mx
    from monte_neo.core.acceleration.engine import GpuAccelerationEngine
    from monte_neo.core.acceleration.tensor_ops import TensorOps
    HAS_MLX = True
except ImportError:
    HAS_MLX = False

from monte_neo.indicators.base import BaseIndicator, IndicatorConfig


class SimpleMLXIndicator(BaseIndicator):
    """Simple indicator compatible with MLX."""
    def __init__(self):
        super().__init__(IndicatorConfig(name="MLX_SMA", parameters={"period": 5}))
        self.period = 5

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        # Not used in pure GPU path
        return data

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        # Not used in pure GPU path
        return data

    def to_mlx_representation(self) -> dict | None:
        return {
            "type": "sma_crossover",
            "period": self.period,
            "params": [self.period]
        }


@pytest.mark.skipif(not HAS_MLX, reason="MLX not available")
class TestGpuCore:
    def setup_method(self):
        self.engine = GpuAccelerationEngine()
        # Create dummy data
        n = 100
        self.data = pd.DataFrame({
            "open": np.random.rand(n) + 100,
            "high": np.random.rand(n) + 101,
            "low": np.random.rand(n) + 99,
            "close": np.random.rand(n) + 100,
            "volume": np.random.rand(n) * 1000
        })

    def test_tensor_ops_creation(self):
        """Test basic tensor operations."""
        prices = np.array([1, 2, 3, 4, 5], dtype=np.float32)
        mx_prices = mx.array(prices)
        assert mx_prices.shape[0] == 5
        
        # Test MA
        ma = TensorOps.moving_average(mx_prices, 2)
        assert ma.shape[0] == 5
        # [1, 1.5, 2.5, 3.5, 4.5] (first element padded/handled)
        
    def test_pure_gpu_execution(self):
        """Test full simulation pipeline on GPU."""
        indicator = SimpleMLXIndicator()
        
        # Run small simulation
        results = self.engine.run_simulation(
            data=self.data,
            mlx_strategy=indicator.to_mlx_representation(),
            n_scenarios=50,
            method="shuffling",
            seed=42
        )
        
        assert len(results) == 50
        assert "passed" in results[0]
        assert "metrics" in results[0]
        assert "profit_factor" in results[0]["metrics"]

    def test_noise_method(self):
        """Test noise injection method on GPU."""
        indicator = SimpleMLXIndicator()
        results = self.engine.run_simulation(
            data=self.data,
            mlx_strategy=indicator.to_mlx_representation(),
            n_scenarios=20,
            method="noise",
            seed=123
        )
        assert len(results) == 20

    def test_performance_check(self):
        """Simple check that it runs fast enough (smoke test)."""
        indicator = SimpleMLXIndicator()
        import time
        start = time.time()
        _ = self.engine.run_simulation(
            data=self.data,
            mlx_strategy=indicator.to_mlx_representation(),
            n_scenarios=1000,
            method="shuffling"
        )
        elapsed = time.time() - start
        # 1000 scenarios should be instant on GPU
        assert elapsed < 2.0  # Very generous limit
