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
    assert by_rule["full_sample_stat"] == [8, 12]
    assert by_rule["full_sample_fit"] == [13]
    assert res["status"] == "fail"
