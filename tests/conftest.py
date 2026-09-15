"""Pytest configuration."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
    data = pd.DataFrame(
        {
            "open": np.linspace(100, 110, 100),
            "high": np.linspace(101, 111, 100),
            "low": np.linspace(99, 109, 100),
            "close": np.linspace(100.5, 110.5, 100),
            "volume": np.random.uniform(1000, 2000, 100),
        },
        index=dates,
    )
    return data


@pytest.fixture
def sample_signals(sample_ohlcv):
    """Create sample signals."""
    signals = pd.DataFrame(index=sample_ohlcv.index)
    signals["signal"] = 0
    # Simple alternating signals
    signals.iloc[10, 0] = 1  # Buy
    signals.iloc[20, 0] = -1  # Sell
    signals.iloc[30, 0] = 1  # Buy
    signals.iloc[40, 0] = -1  # Sell
    return signals
