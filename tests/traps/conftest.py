"""Datasets for the verifier trap suite."""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv


def planted_momentum_ohlcv(n: int = 5000, phi: float = 0.15, sigma: float = 0.005, seed: int = 7) -> pd.DataFrame:
    """Hourly bars whose returns follow AR(1) with ``phi`` > 0 (a real, causal edge)."""
    rng = np.random.default_rng(seed)
    eps = rng.normal(0.0, sigma, n)
    rets = np.zeros(n)
    for i in range(1, n):
        rets[i] = phi * rets[i - 1] + eps[i]
    close = 100.0 * np.exp(np.cumsum(rets))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    wiggle = rng.uniform(0.0001, 0.001, n)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC"),
            "open": open_,
            "high": np.maximum(open_, close) * (1.0 + wiggle),
            "low": np.minimum(open_, close) * (1.0 - wiggle),
            "close": close,
        }
    )


@pytest.fixture(scope="session")
def random_walk(tmp_path_factory: pytest.TempPathFactory) -> pd.DataFrame:
    """Minute bars without any edge (also on disk for the reads_dataset_file trap)."""
    df = synthetic_ohlcv(3000, seed=1)
    path = tmp_path_factory.mktemp("trap-data") / "prices.csv"
    df.to_csv(path, index=False)
    os.environ["MONTE_NEO_TRAP_DATA"] = str(path)
    return df


@pytest.fixture(scope="session")
def planted() -> pd.DataFrame:
    """Hourly bars with a planted momentum edge."""
    return planted_momentum_ohlcv()
