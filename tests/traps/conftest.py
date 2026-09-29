"""Datasets for the verifier trap suite."""

from __future__ import annotations

import os

import pandas as pd
import pytest
from trap_data import bad_tick_ohlcv, frozen_ohlcv, outage_ohlcv, planted_momentum_ohlcv, split_ohlcv, universe_ohlcv

from monte_neo.backtest import synthetic_ohlcv


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


@pytest.fixture(scope="session")
def universe() -> pd.DataFrame:
    """Six daily random walks: one listed late, one delisted."""
    return universe_ohlcv()


@pytest.fixture(scope="session")
def bad_ticks() -> pd.DataFrame:
    """Hourly random walk with 40 one-bar bad ticks."""
    return bad_tick_ohlcv()


@pytest.fixture(scope="session")
def frozen_feed() -> pd.DataFrame:
    """Hourly random walk with six frozen stretches."""
    return frozen_ohlcv()


@pytest.fixture(scope="session")
def unadjusted_split() -> pd.DataFrame:
    """Hourly random walk with an unadjusted 2-for-1 split."""
    return split_ohlcv()


@pytest.fixture(scope="session")
def feed_outages() -> pd.DataFrame:
    """Hourly random walk with two outages."""
    return outage_ohlcv()
