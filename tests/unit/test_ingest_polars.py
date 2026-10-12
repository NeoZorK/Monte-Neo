"""``load_ohlcv`` accepts a polars DataFrame (duck-typed, polars not imported) and parquet files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify.ingest import as_pandas, load_ohlcv


def _fake_polars(frame: pd.DataFrame) -> object:
    cls = type("DataFrame", (), {"__module__": "polars.dataframe.frame", "to_pandas": lambda self: frame})
    return cls()


def test_polars_like_object_is_converted() -> None:
    frame = synthetic_ohlcv(50, seed=1)
    out = load_ohlcv(_fake_polars(frame))
    assert list(out["close"]) == list(frame["close"])


def test_other_objects_with_to_pandas_are_not_touched() -> None:
    cls = type("Thing", (), {"__module__": "somelib", "to_pandas": lambda self: None})
    thing = cls()
    assert as_pandas(thing) is thing


def test_parquet_round_trip(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    frame = synthetic_ohlcv(60, seed=2)
    path = tmp_path / "bars.parquet"
    frame.to_parquet(path)
    out = load_ohlcv(path)
    assert len(out) == 60 and out["close"].dtype == "float64"
