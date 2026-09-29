"""Pytest configuration."""

import importlib.util
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# MLX exists only on Apple Silicon: without it, modules that import it at the top are not collected.
HAS_MLX = importlib.util.find_spec("mlx") is not None
_TOP_LEVEL_MLX = re.compile(r"^(import mlx|from mlx)\b", re.MULTILINE)


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """Skip test modules that need MLX on machines without it."""
    if HAS_MLX or collection_path.suffix != ".py" or not collection_path.name.startswith("test_"):
        return None
    try:
        text = collection_path.read_text(encoding="utf-8")
    except OSError:
        return None
    return True if _TOP_LEVEL_MLX.search(text) else None


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
