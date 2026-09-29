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


# Research-engine tests that need MLX or the Metal GPU at run time. They run on the macOS CI job;
# on machines without MLX (Linux) they are skipped instead of failing.
APPLE_ONLY = {
    "tests/unit/legacy_coverage/test_coverage_boost5.py::test_signal_factory_fallbacks",
    "tests/unit/test_coverage_rest.py::test_tensor_ops",
    "tests/unit/test_gpu_engine_parallel.py::test_backtest_batch_parallel_for_dynamic",
    "tests/unit/test_gpu_lazy.py::test_backtest_lazy_scenarios_no_sl_tp",
    "tests/unit/test_gpu_scenarios.py::test_run_scenarios_backtest_no_sl_tp",
    "tests/unit/test_mc_engine.py::test_run_gpu_full_simulation",
    "tests/unit/test_mc_engine.py::test_run_lazy_block_bootstrap",
    "tests/unit/test_mlx_engine.py::test_backtest_batch_parallel",
    "tests/unit/test_mlx_engine.py::test_backtest_batch_sequential",
    "tests/unit/test_monte_carlo.py::test_mc_run",
    "tests/unit/test_monte_carlo.py::test_mc_run_sequential",
    "tests/unit/test_monte_carlo_engine.py::TestMonteCarloEngine::test_meets_targets_mdd_consecutive_losses",
    "tests/unit/test_monte_carlo_engine.py::TestMonteCarloEngine::test_run_block_bootstrap_lazy",
    "tests/unit/test_monte_carlo_engine.py::TestMonteCarloEngine::test_run_existing_scenarios",
    "tests/unit/test_monte_carlo_engine.py::TestMonteCarloEngine::test_run_progress_callbacks",
    "tests/unit/test_monte_carlo_engine.py::TestMonteCarloEngine::test_run_pure_gpu_mlx",
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip the Apple-only research tests where MLX is not installed."""
    if HAS_MLX:
        return
    skip = pytest.mark.skip(reason="needs MLX / Metal (Apple Silicon)")
    for item in items:
        if item.nodeid.split("[")[0] in APPLE_ONLY:
            item.add_marker(skip)


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
