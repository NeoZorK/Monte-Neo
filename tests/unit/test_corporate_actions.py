"""Corporate actions: declared splits and dividends against prices."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify.corporate_actions import (
    corporate_actions_row,
    dividend_income,
    parse_actions,
    total_return_adjust,
)

N = 400
RNG = np.random.default_rng(8)


def _ohlc(split_at: int | None = None, ratio: float = 2.0) -> dict[str, np.ndarray]:
    c = 100 * np.cumprod(1 + RNG.normal(0.0003, 0.008, N))
    if split_at is not None:
        c[split_at:] /= ratio  # an unadjusted split: the price drops by the ratio
    o = np.r_[c[0], c[:-1]]
    return {"open": o, "high": np.maximum(o, c) * 1.002, "low": np.minimum(o, c) * 0.998, "close": c}


def test_unadjusted_declared_split_fails() -> None:
    o = _ohlc(split_at=200)
    row = corporate_actions_row(o, [(200, "split", 2.0)], np.ones(N), 0.1)
    assert row["status"] == "fail" and "still in the prices" in row["summary"]


def test_adjusted_declared_split_passes() -> None:
    o = _ohlc()
    assert corporate_actions_row(o, [(200, "split", 2.0)], np.ones(N), 0.1)["status"] == "pass"


def test_undeclared_jump_warns_and_declaring_it_clears_it() -> None:
    o = _ohlc(split_at=150, ratio=4.0)
    warn = corporate_actions_row(o, [], np.ones(N), 0.1)
    assert warn["status"] == "warn" and "no declared action" in warn["summary"]
    assert corporate_actions_row(o, [(150, "split", 4.0)], np.ones(N), 0.1)["status"] == "fail"  # now declared: still unadjusted


def test_reverse_split_is_matched() -> None:
    o = _ohlc(split_at=100, ratio=0.5)  # price doubles at a 1-for-2 reverse split
    assert corporate_actions_row(o, [(100, "split", 0.5)], np.ones(N), 0.1)["status"] == "fail"


def test_dividend_income_long_short_and_materiality() -> None:
    o = _ohlc()
    acts = [(b, "dividend", 1.0) for b in (50, 150, 250, 350)]  # about 1 % each: 4 % over the test
    long_row = corporate_actions_row(o, acts, np.ones(N), 0.2)
    short_row = corporate_actions_row(o, acts, -np.ones(N), 0.2)
    assert long_row["status"] == "warn" and "collects" in long_row["summary"]
    assert short_row["status"] == "warn" and "pays" in short_row["summary"]
    small = corporate_actions_row(o, [(50, "dividend", 0.05)], np.ones(N), 0.2)
    assert small["status"] == "pass"
    flat = corporate_actions_row(o, acts, np.zeros(N), 0.2)
    assert flat["status"] == "pass" and flat["details"]["dividend_income"] == 0.0


def test_total_return_adjust_removes_the_ex_date_gap() -> None:
    o = _ohlc()
    adj = total_return_adjust(o, [(100, "dividend", 2.0)])
    f = 1.0 - 2.0 / o["close"][99]
    assert adj["close"][99] == pytest.approx(o["close"][99] * f) and adj["close"][100] == o["close"][100]
    assert dividend_income(np.ones(N), o["close"], [(100, "dividend", 2.0)]) == pytest.approx(2.0 / o["close"][99])
    split = total_return_adjust(o, [(100, "split", 2.0)], splits=True)
    assert split["close"][0] == pytest.approx(o["close"][0] / 2.0)
    assert total_return_adjust(o, [(100, "split", 2.0)])["close"][0] == o["close"][0]  # splits untouched unless asked
    with pytest.raises(ValueError, match="not below"):
        total_return_adjust(o, [(100, "dividend", 1e6)])


def test_parse_actions_validation_and_dates() -> None:
    assert parse_actions([], 100) == []
    assert parse_actions([{"bar": 5, "kind": "split", "value": 2}, {"bar": 3, "kind": "dividend", "value": 1}], 100) == [(3, "dividend", 1.0), (5, "split", 2.0)]
    for bad in (
        [{"bar": 5, "kind": "merger", "value": 2}], [{"bar": 5, "kind": "split", "value": -1}], [{"bar": 0, "kind": "split", "value": 2}],
        [{"bar": 100, "kind": "split", "value": 2}], [{"kind": "split", "value": 2}],
        [{"bar": 5, "kind": "split", "value": 2}, {"bar": 5, "kind": "split", "value": 3}],
    ):
        with pytest.raises(ValueError):
            parse_actions(bad, 100)
    ts = pd.date_range("2024-01-01", periods=100, freq="D", tz="UTC")
    assert parse_actions([{"date": "2024-01-11", "kind": "split", "value": 2}], 100, ts) == [(10, "split", 2.0)]
    with pytest.raises(ValueError, match="after the last"):
        parse_actions([{"date": "2030-01-01", "kind": "split", "value": 2}], 100, ts)
    with pytest.raises(ValueError, match="needs timestamps"):
        parse_actions([{"date": "2024-01-11", "kind": "split", "value": 2}], 100)


def test_verify_reads_declared_actions_and_recheck_keeps_them() -> None:
    from monte_neo.backtest import synthetic_ohlcv
    from monte_neo.verify import verify_strategy

    df = synthetic_ohlcv(500, seed=9)
    sig = np.ones(500, dtype=int)
    clean = verify_strategy(df, signals=sig, corporate_actions=[{"bar": 100, "kind": "dividend", "value": 0.01}])
    row = {c["id"]: c for c in clean["checks"]}["corporate_actions"]
    assert row["status"] == "pass" and clean["reproducibility"]["settings"]["corporate_actions"] == [[100, "dividend", 0.01]]
    assert "corporate_actions" not in {c["id"] for c in verify_strategy(df, signals=sig)["checks"]}
    big = verify_strategy(df, signals=sig, corporate_actions=[{"bar": 100, "kind": "dividend", "value": float(df["close"].iloc[99]) * 0.05}])
    assert {c["id"]: c for c in big["checks"]}["corporate_actions"]["status"] == "warn"
