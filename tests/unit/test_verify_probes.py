"""Unit tests for look-ahead probes, static lint and cost stress."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import ExecutionModel, synthetic_ohlcv
from monte_neo.verify import (
    breakeven_cost_bps,
    delay_scan,
    delay_signals,
    implausible_accuracy,
    lint_source,
    mirror_future,
    probe_determinism,
    probe_perturbation,
    probe_truncation,
)
from monte_neo.verify.lookahead import _checkpoints, _hit_rate


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return synthetic_ohlcv(400, seed=3)


def _causal(d: pd.DataFrame) -> np.ndarray:
    return (d["close"] > d["close"].rolling(10).mean()).astype(int).to_numpy()


def _leaky(d: pd.DataFrame) -> np.ndarray:
    return np.sign(d["close"].shift(-1) - d["close"]).to_numpy()


def test_checkpoints_edges() -> None:
    assert _checkpoints(3, 5, None).tolist() == [1]
    assert _checkpoints(2, 5, None).size == 0
    pts = _checkpoints(100, 4, 10)
    assert pts[0] == 10 and pts[-1] == 98


def test_truncation_and_perturbation(df) -> None:
    assert probe_truncation(_causal, df)["status"] == "pass"
    bad = probe_truncation(_leaky, df, n_checks=8)
    assert bad["status"] == "fail" and bad["first_mismatch_bar"] is not None
    assert probe_perturbation(_causal, df)["status"] == "pass"
    assert probe_perturbation(_leaky, df, n_checks=3)["status"] == "fail"
    tiny = df.iloc[:2].reset_index(drop=True)
    assert probe_truncation(_causal, tiny)["status"] == "skip"


def test_determinism(df) -> None:
    assert probe_determinism(_causal, df)["status"] == "pass"
    rng = np.random.default_rng()

    def noisy(d: pd.DataFrame) -> np.ndarray:
        return rng.integers(-1, 2, size=len(d))

    res = probe_determinism(noisy, df)
    assert res["status"] == "fail" and res["differing_bars"] > 0


def test_mirror_future(df) -> None:
    alt = mirror_future(df, 100)
    assert np.allclose(alt["close"].iloc[:101], df["close"].iloc[:101])
    assert not np.allclose(alt["close"].iloc[150:], df["close"].iloc[150:])
    assert (alt["high"] >= alt["low"]).all()
    assert mirror_future(df, len(df) - 1).equals(df)


def test_implausible_accuracy(df) -> None:
    o, c = df["open"].to_numpy(), df["close"].to_numpy()
    assert implausible_accuracy(o, c, np.array([1, 0]))["status"] == "skip"
    assert implausible_accuracy(o, c, np.zeros(len(c), dtype=int))["status"] == "skip"
    leak = _leaky(df)
    assert implausible_accuracy(o, c, leak)["status"] == "fail"
    honest = implausible_accuracy(o, c, _causal(df), min_active=10)
    assert honest["status"] == "pass"
    # Body-only leak (close vs next open) is caught by the second hit rate.
    o2 = o * np.where(np.arange(len(o)) % 2 == 0, 1.002, 0.998)
    body = np.zeros(len(c), dtype=int)
    body[:-1] = np.sign(c[1:] - o2[1:])
    res = implausible_accuracy(o2, c, body, min_active=10)
    assert res["hit_rate"] == res["hit_rate_next_bar_body"]
    assert _hit_rate(np.array([0, 0]), np.array([1.0, 1.0])) == (0.5, 0)


def test_lint_rules() -> None:
    src = """
import numpy as np
def signal(df):
    a = df.close.shift(-2)
    b = df.close.shift(periods=-1)
    c = df.close.shift(1)
    d = df.close.shift(-x)
    e = df.close.rolling(5, center=True).mean()
    f = df.close.bfill()
    g = df.close.fillna(method="backfill")
    h = model.fit(df)
    i = df.close.values[t + 1]
    j = df.close.values[t + k]
    return a
"""
    res = lint_source(src)
    assert res["status"] == "fail"
    rules = [f["rule"] for f in res["findings"]]
    assert rules.count("negative_shift") == 2
    for rule in ("centered_window", "backward_fill", "full_sample_fit", "forward_index"):
        assert rule in rules
    assert rules.count("backward_fill") == 2
    assert lint_source("x = model.fit_transform(df)")["status"] == "warn"
    assert lint_source("def signal(df):\n    return df.close.shift(1)\n") == {"status": "pass", "findings": []}
    assert lint_source("def (")["status"] == "skip"


def test_costs(df) -> None:
    ohlc = {k: df[k].to_numpy() for k in ("open", "high", "low", "close")}
    model = ExecutionModel(warmup_bars=10)
    loser = np.where(np.arange(len(df)) % 2 == 0, 1, 0)
    down = breakeven_cost_bps(ohlc, loser, model)
    assert down["breakeven_bps"] == 0.0 or down["gross_return"] > 0.0
    perfect = np.zeros(len(df), dtype=int)
    perfect[:-1] = (df["close"].to_numpy()[1:] > df["open"].to_numpy()[1:]).astype(int)
    be = breakeven_cost_bps(ohlc, perfect, model, max_bps=500.0)
    assert be["bounded"] and 0.0 < be["breakeven_bps"] < 500.0
    capped = breakeven_cost_bps(ohlc, perfect, model, max_bps=0.01)
    assert capped == {"breakeven_bps": 0.01, "gross_return": capped["gross_return"], "bounded": False}
    flat = breakeven_cost_bps(ohlc, np.zeros(len(df), dtype=int), model)
    assert flat["breakeven_bps"] == 0.0
    scan = delay_scan(ohlc, perfect, ExecutionModel(warmup_bars=10, commission_bps=1.0, slippage_bps=0.0))
    assert scan["status"] == "warn" and scan["fragile_to_one_bar_delay"]
    assert delay_scan(ohlc, np.ones(len(df), dtype=int), model)["status"] == "pass"


def test_delay_signals() -> None:
    s = np.array([1, 0, -1])
    assert delay_signals(s, 0).tolist() == [1, 0, -1]
    assert delay_signals(s, 1).tolist() == [0, 1, 0]
    assert delay_signals(s, 5).tolist() == [0, 0, 0]
