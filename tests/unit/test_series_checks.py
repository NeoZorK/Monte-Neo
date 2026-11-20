"""data_integrity and an honest ARL for inputs without OHLCV (returns and legs)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.verify.legs import verify_legs
from monte_neo.verify.returns_dd import demo_returns, verify_returns
from monte_neo.verify.series_checks import FROZEN_RUN, series_integrity

IDX = pd.date_range("2024-01-01", periods=60, freq="D")


def _legs(n: int = 80, seed: int = 2) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    px_y, px_x = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), 50 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    q = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=n, freq="D"), "px_y": px_y, "px_x": px_x,
                       "qty_y": q, "qty_x": -q, "reported_return": 0.0})
    body = df.set_index("date")
    rep = q[1:] * np.diff(np.log(px_y)) - q[1:] * np.diff(np.log(px_x))
    body["reported_return"] = np.concatenate([[0.0], rep])
    return body


def test_clean_series_passes_and_reaches_level_one() -> None:
    rep = verify_returns(demo_returns(0)["honest"])
    row = next(c for c in rep["checks"] if c["id"] == "data_integrity")
    assert row["status"] == "pass"
    ready = rep["readiness"]
    assert ready["level"] == 1 and ready["of"] == 9
    assert "missing evidence, not failures" in ready["scope"]
    assert ready["levels"][1]["state"] == "not assessed"  # level 2 needs look-ahead evidence: never invented


def test_legs_gets_meaningful_arl_not_zero() -> None:
    rep = verify_legs(_legs())
    assert any(c["id"] == "data_integrity" and c["status"] == "pass" for c in rep["checks"])
    assert rep["readiness"]["level"] == 1
    assert "legs" in rep["readiness"]["scope"]


def test_arl_never_exceeds_one_without_ohlcv() -> None:
    for rep in (verify_returns(demo_returns(0)["too_good"]), verify_legs(_legs())):
        assert rep["readiness"]["level"] <= 1
        assert all(lv["state"] != "met" for lv in rep["readiness"]["levels"][1:])


def test_broken_series_gives_arl_zero() -> None:
    r = pd.Series(np.random.default_rng(1).normal(0.001, 0.02, 60), IDX)
    r.iloc[10] = -1.2
    rep = verify_returns(r)
    row = next(c for c in rep["checks"] if c["id"] == "data_integrity")
    assert row["status"] == "fail" and "-100%" in row["summary"]
    assert rep["readiness"]["level"] == 0


def test_unordered_and_nonfinite_fail() -> None:
    idx = pd.DatetimeIndex(list(IDX[:5]) + [IDX[2]] + list(IDX[6:10]))
    row = series_integrity(idx, np.full(idx.size, 0.001))
    assert row["status"] == "fail" and row["details"]["out_of_order_dates"] == 1
    row = series_integrity(IDX[:3], np.array([0.1, np.nan, 0.0]))
    assert row["status"] == "fail" and row["details"]["non_finite"] == 1
    row = series_integrity(IDX[[0, 0, 1]], np.array([0.1, 0.0, 0.0]))
    assert row["details"]["duplicate_dates"] == 1


def test_gap_and_frozen_warn_boundary() -> None:
    idx = IDX.delete(slice(20, 30))  # a 11-day hole in daily data
    r = np.random.default_rng(0).normal(0.0, 0.01, idx.size)
    assert series_integrity(idx, r)["status"] == "warn"
    weekend = pd.bdate_range("2024-01-01", periods=60)  # 3-day weekends are normal, not a gap
    assert series_integrity(weekend, np.random.default_rng(0).normal(0, 0.01, 60))["status"] == "pass"
    frozen = np.random.default_rng(0).normal(0, 0.01, 60)
    frozen[5:5 + FROZEN_RUN] = 0.003
    assert series_integrity(IDX, frozen)["status"] == "warn"
    frozen[5:5 + FROZEN_RUN - 1] = 0.003
    frozen[5 + FROZEN_RUN - 1] = 0.0031
    assert series_integrity(IDX, frozen)["status"] == "pass"


def test_price_frozen_and_jump_warn() -> None:
    r = np.zeros(60)
    px = {"y": 100 * np.exp(np.cumsum(np.random.default_rng(0).normal(0, 0.01, 60)))}
    assert series_integrity(IDX, r, px)["status"] == "pass"
    px["y"][20:20 + FROZEN_RUN] = px["y"][20]
    assert series_integrity(IDX, r, px)["details"]["longest_frozen_price_run"] >= FROZEN_RUN
    jump = {"y": np.concatenate([np.full(30, 100.0) * np.exp(np.arange(30) * 0.001), np.full(30, 40.0)])}
    row = series_integrity(IDX, r, jump)
    assert row["status"] == "warn" and row["details"]["price_jumps"] == 1


def test_empty_series_helpers() -> None:
    row = series_integrity(IDX[:0], np.array([]))
    assert row["status"] == "pass"
