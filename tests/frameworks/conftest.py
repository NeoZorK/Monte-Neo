"""Real-framework tests: each one runs a backtest in the framework and compares what the adapter reads
with the position the framework itself held. They are skipped when the framework is not installed."""

from __future__ import annotations

import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv

BARS = 1500


@pytest.fixture(scope="session")
def prices() -> pd.DataFrame:
    """Daily bars with a timestamp column; the same table feeds every framework."""
    df = synthetic_ohlcv(BARS, seed=3)
    df["timestamp"] = pd.date_range("2020-01-01", periods=len(df), freq="D")
    return df
