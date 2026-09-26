"""Unit tests for verify_grid, walk-forward and the new lint rules."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import expand_grid, lint_source, verify_grid, walk_forward
from monte_neo.verify.grid import MAX_COMBOS, walk_forward_row


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return synthetic_ohlcv(1200, seed=4)


def sma(d: pd.DataFrame, fast: int = 10, slow: int = 40) -> np.ndarray:
    return (d["close"].rolling(fast).mean() > d["close"].rolling(slow).mean()).astype(int).to_numpy()


def test_expand_grid() -> None:
    assert expand_grid({"b": [1, 2], "a": ["x"]}) == [{"a": "x", "b": 1}, {"a": "x", "b": 2}]
    with pytest.raises(ValueError, match="at least one parameter"):
        expand_grid({})
    with pytest.raises(ValueError, match="at least one value"):
        expand_grid({"a": []})
    with pytest.raises(ValueError, match="max"):
        expand_grid({"a": list(range(MAX_COMBOS + 1))})


def test_walk_forward_and_row() -> None:
    rng = np.random.default_rng(0)
    rets = rng.normal(0.0, 0.01, size=(3, 500))
    rets[1] += 0.002  # combo 1 has a persistent edge
    wf = walk_forward(rets, folds=3)
    assert wf["chosen_combo_per_fold"] == [1, 1, 1]
    assert wf["param_stability"] == 1.0 and wf["oos_sharpe"] > 0.0
    assert walk_forward_row(wf, wf["oos_sharpe"])["status"] == "pass"
    assert walk_forward_row(wf, 10 * wf["oos_sharpe"])["status"] == "warn"
    assert walk_forward_row({**wf, "oos_sharpe": -0.1}, 0.2)["status"] == "fail"
    assert walk_forward(rets, folds=0)["oos_bars"] == 0


def test_verify_grid_signal_fn(df) -> None:
    report = verify_grid(df, {"fast": [5, 10], "slow": [40]}, signal_fn=sma, source="x = 1\n", folds=2)
    assert report["grid"]["n_combos"] == 2
    assert report["reproducibility"]["n_trials"] == 2
    assert report["reproducibility"]["extra_sha256"]
    assert any(c["id"] == "walk_forward_oos" for c in report["checks"])
    single = verify_grid(df, {"fast": [5], "slow": [40]}, signal_fn=sma, folds=2)
    assert single["checks"][[c["id"] for c in single["checks"]].index("deflated_sharpe")]["details"]["sr_variance_source"] == "null_sampling_variance"
    with pytest.raises(ValueError, match="strategy= or signal_fn="):
        verify_grid(df, {"fast": [5]})


def test_new_lint_rules() -> None:
    src = """
def signal(df, np=None):
    a = df.close[::-1].rolling(5).max()[::-1]
    b = df.close.rank(pct=True)
    c = df.close.rolling(20).rank()
    d = df.groupby(df.day)["close"].transform("last")
    e = df.groupby(df.day)["close"].transform(lambda s: s)
    f = df["close"].mean()
    g = np.mean(df.close)
    h = df.close.rolling(3).std()
    i = np.random.rand(3).max()
    j = close.max()
    k = np.polyfit(x, y, 2)
    m = df.close[::2].rolling(3).mean()
    return a
"""
    res = lint_source(src)
    by_rule: dict[str, list[int]] = {}
    for f in res["findings"]:
        by_rule.setdefault(f["rule"], []).append(f["line"])
    assert by_rule["reversed_window"] == [3]
    assert by_rule["full_sample_rank"] == [4]
    assert by_rule["group_aggregate"] == [6]
    assert by_rule["full_sample_stat"] == [8, 9, 12]
    assert by_rule["full_sample_fit"] == [13]
    assert res["status"] == "fail"


def test_lint_negative_periods_roll_asof_interpolate() -> None:
    src = """
def signal(df):
    a = df.close.diff(-1)
    b = df.close.pct_change(periods=-2)
    c = df.close.diff(1)
    d = np.roll(x, -1)
    e = np.roll(x, 1)
    f = pd.merge_asof(a, b, on="t", direction="forward")
    g = pd.merge_asof(a, b, on="t")
    h = s.interpolate()
    i = s.interpolate(method="ffill")
    j = df.volume.sum()
    return a
"""
    by_rule: dict[str, list[int]] = {}
    for f in lint_source(src)["findings"]:
        by_rule.setdefault(f["rule"], []).append(f["line"])
    assert by_rule["negative_period"] == [3, 4]
    assert by_rule["negative_roll"] == [6]
    assert by_rule["forward_asof"] == [8]
    assert by_rule["interpolate"] == [10]
    assert by_rule["full_sample_stat"] == [12]


def test_lint_last_row_idxmax_and_numpy_stats() -> None:
    src = """
def signal(df):
    a = df.close.iloc[-1]
    b = df.close.values[-2]
    c = df.close.to_numpy()[-1]
    d = df.close.iloc[1]
    e = lst[-1]
    f = df.close.idxmax()
    g = np.mean(close)
    h = np.mean(np.array([1, 2]))
    i = numpy.std(df.close)
    j = np.mean([1, 2])
    k = np.clip(close, 0, 1)
    return a
"""
    by_rule: dict[str, list[int]] = {}
    for f in lint_source(src)["findings"]:
        by_rule.setdefault(f["rule"], []).append(f["line"])
    assert by_rule["last_row"] == [3, 4, 5]
    assert by_rule["full_sample_stat"] == [8, 9, 11]


def test_lint_signal_processing_rules() -> None:
    src = """
def signal(df):
    a = np.gradient(close)
    b = np.convolve(close, k, mode="same")
    c = np.convolve(close, k, "same")
    d = np.convolve(close, k, mode="full")
    e = np.correlate(close, k)
    f = signal.filtfilt(b, a, close)
    g = savgol_filter(close, 11, 2) + scipy.signal.savgol_filter(close, 11, 2)
    h = np.fft.rfft(close)
    i = np.fft.irfft(h)
    j = pd.qcut(ret, 5, labels=False)
    k = np.argsort(np.argsort(close))
    return a
"""
    by_rule: dict[str, list[int]] = {}
    for f in lint_source(src)["findings"]:
        by_rule.setdefault(f["rule"], []).append(f["line"])
    assert by_rule["central_difference"] == [3]
    assert by_rule["centered_filter"] == [4, 5, 8, 9]
    assert by_rule["full_sample_transform"] == [10]
    assert by_rule["full_sample_rank"] == [12, 13]


def test_lint_calendar_and_reversed_rules() -> None:
    src = """
def signal(df):
    a = s[::-1].cummax()[::-1]
    b = np.cumsum(x[::-1])
    c = s.cumsum()
    d = h.reindex(idx, method="nearest")
    e = h.reindex(idx, method="ffill")
    f = df.groupby(g).cumcount(ascending=False)
    k = df.groupby(g).cumcount()
    m = df.groupby(g)["close"].last()
    n = df.groupby(g)["close"].last().shift(1)
    o = df.groupby(g)["close"].transform("size")
    p = s.sort_values()
    q = df.sort_values("timestamp")
    return a
"""
    by_rule: dict[str, list[int]] = {}
    for f in lint_source(src)["findings"]:
        by_rule.setdefault(f["rule"], []).append(f["line"])
    assert by_rule["reversed_cumulative"] == [3, 4]
    assert by_rule["backward_fill"] == [6]
    assert by_rule["reverse_count"] == [8]
    assert by_rule["group_aggregate"] == [10, 12]
    assert by_rule["full_sample_rank"] == [13]


def test_lint_forward_indexer_tail_builtins() -> None:
    src = """
def signal(df):
    a = df.close.rolling(window=pd.api.indexers.FixedForwardWindowIndexer(window_size=5)).max()
    b = FixedForwardWindowIndexer(window_size=5)
    c = df.close.tail(100).mean()
    d = df.close.iat[-1]
    e = np.sort(close)
    f = pd.cut(close, bins=5)
    g = pd.cut(close, [0, 1, 2])
    h = np.maximum.accumulate(x[::-1])
    i = max(df.close)
    j = max(a, b)
    k = sorted(values, key=abs)
    return a
"""
    by_rule: dict[str, list[int]] = {}
    for f in lint_source(src)["findings"]:
        by_rule.setdefault(f["rule"], []).append(f["line"])
    assert by_rule["forward_window"] == [3, 4]
    assert by_rule["last_row"] == [5, 6]
    assert by_rule["full_sample_rank"] == [7, 8]
    assert by_rule["reversed_cumulative"] == [10]
    assert by_rule["full_sample_stat"] == [11]
