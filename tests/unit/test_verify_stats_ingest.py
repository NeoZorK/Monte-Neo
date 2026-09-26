"""Unit tests for verifier statistics and input loading."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify import (
    bar_returns,
    call_signal_fn,
    deflated_sharpe,
    expected_max_sharpe,
    infer_periods_per_year,
    load_ohlcv,
    load_signal_fn,
    load_signals,
    normalize_signals,
    probabilistic_sharpe,
    sharpe_per_bar,
)
from monte_neo.verify.stats import _moments


def test_bar_returns_edges() -> None:
    assert bar_returns(np.array([1.0])).size == 0
    r = bar_returns(np.array([100.0, 0.0, 50.0, 55.0]))
    assert r[0] == pytest.approx(-1.0)
    assert r[1] == 0.0  # previous equity 0 -> undefined -> 0
    assert r[2] == pytest.approx(0.1)
    assert bar_returns(np.array([1.0, 2.0, 4.0]), start=1).tolist() == [1.0]


def test_sharpe_and_moments_degenerate() -> None:
    assert sharpe_per_bar(np.array([0.1])) == 0.0
    assert sharpe_per_bar(np.zeros(10)) == 0.0
    assert sharpe_per_bar(np.array([0.01, 0.03])) > 0.0
    assert _moments(np.zeros(5)) == (0.0, 3.0)
    skew, kurt = _moments(np.array([0.0, 0.0, 0.0, 1.0]))
    assert skew > 0.0 and kurt > 1.0


def test_psr_and_expected_max() -> None:
    assert probabilistic_sharpe(0.1, 1) == 0.0
    assert probabilistic_sharpe(0.0, 100) == pytest.approx(0.5)
    # Pathological moments force the denominator floor instead of a crash.
    assert probabilistic_sharpe(1.0, 100, skew=10.0, kurt=3.0) == pytest.approx(1.0)
    assert expected_max_sharpe(1, 0.01) == 0.0
    assert expected_max_sharpe(10, 0.0) == 0.0
    e10, e1000 = expected_max_sharpe(10, 0.01), expected_max_sharpe(1000, 0.01)
    assert 0.0 < e10 < e1000


def test_deflated_sharpe_penalizes_trials() -> None:
    rng = np.random.default_rng(0)
    r = rng.normal(0.0005, 0.01, 2000)
    one = deflated_sharpe(r, n_trials=1)
    many = deflated_sharpe(r, n_trials=500)
    assert one["deflated_sharpe"] == pytest.approx(one["psr"])
    assert many["deflated_sharpe"] < one["deflated_sharpe"]
    assert many["sr_variance_source"] == "null_sampling_variance"
    custom = deflated_sharpe(r, n_trials=50, trial_sharpes=np.array([0.0, 0.01, 0.02]), periods_per_year=365)
    assert custom["sr_variance_source"] == "trial_sharpes"
    assert custom["sharpe_annualized"] == pytest.approx(custom["sharpe_per_bar"] * math.sqrt(365))


def test_infer_periods_per_year() -> None:
    assert infer_periods_per_year(None) == 252.0
    assert infer_periods_per_year(["a", "b", "c"]) == 252.0
    assert infer_periods_per_year(pd.date_range("2020", periods=2, freq="D")) == 252.0
    assert infer_periods_per_year(pd.date_range("2020", periods=5, freq="D")) == pytest.approx(365.25)
    same = pd.to_datetime(["2020-01-01"] * 4)
    assert infer_periods_per_year(same, default=10.0) == 10.0


def _ohlc_frame(n: int = 10) -> pd.DataFrame:
    base = np.linspace(100.0, 101.0, n)
    return pd.DataFrame({"Open": base, "High": base + 1, "Low": base - 1, "Close": base})


def test_load_ohlcv_formats(tmp_path) -> None:
    df = _ohlc_frame().assign(Date=pd.date_range("2020", periods=10, freq="D"))
    csv = tmp_path / "d.csv"
    df.to_csv(csv, index=False)
    out = load_ohlcv(csv)
    assert list(out.columns[:4]) == ["open", "high", "low", "close"]
    assert "timestamp" in out.columns
    pq = tmp_path / "d.parquet"
    df.to_parquet(pq)
    assert len(load_ohlcv(pq)) == 10
    idx = _ohlc_frame().set_index(pd.date_range("2020", periods=10, freq="h"))
    assert "timestamp" in load_ohlcv(idx).columns
    assert "timestamp" not in load_ohlcv(_ohlc_frame()).columns
    with pytest.raises(ValueError, match="unsupported"):
        load_ohlcv(tmp_path / "d.xlsx")
    with pytest.raises(ValueError, match="missing"):
        load_ohlcv(pd.DataFrame({"close": [1.0]}))


def test_signals_normalization_and_files(tmp_path) -> None:
    assert normalize_signals([2.5, -0.1, np.nan, 0.0, np.inf]).tolist() == [1, -1, 0, 0, 1]
    assert normalize_signals(pd.DataFrame({"x": [1, 2], "signal": [-3, 0]})).tolist() == [-1, 0]
    assert normalize_signals(pd.DataFrame({"a": [9, 9], "pos": [1, 0]})).tolist() == [1, 0]
    with pytest.raises(ValueError, match="length"):
        normalize_signals([1, 0], n_bars=3)
    npy = tmp_path / "s.npy"
    np.save(npy, np.array([1, 0, -1]))
    assert load_signals(npy, 3).tolist() == [1, 0, -1]
    csv = tmp_path / "s.csv"
    pd.DataFrame({"signal": [0, 1]}).to_csv(csv, index=False)
    assert load_signals(str(csv)).tolist() == [0, 1]
    assert load_signals([0.5, -2]).tolist() == [1, -1]


def test_load_signal_fn(tmp_path) -> None:
    f = tmp_path / "strat.py"
    f.write_text("def signal(df):\n    return df['close'] * 0 + 1\n\ndef other(df):\n    return -df['close']\n")
    fn, src = load_signal_fn(f)
    assert "def signal" in src
    df = load_ohlcv(_ohlc_frame())
    assert call_signal_fn(fn, df).tolist() == [1] * 10
    other, _ = load_signal_fn(f"{f}:other")
    assert call_signal_fn(other, df).tolist() == [-1] * 10
    with pytest.raises(FileNotFoundError):
        load_signal_fn(tmp_path / "missing.py")
    with pytest.raises(AttributeError):
        load_signal_fn(f"{f}:nope")
