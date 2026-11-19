"""Idle (exact zero) periods must not fake round numbers or a missing-loss kink; real rounding must still be caught."""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.verify import returns_dd_checks as rc
from monte_neo.verify.returns_dd import demo_returns, verify_returns


def _trading(idle: float, n: int = 1000, seed: int = 4) -> np.ndarray:
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0004, 0.02, n)
    r[rng.random(n) < idle] = 0.0
    return r


def _status(rep: dict, cid: str) -> str:
    return next(c["status"] for c in rep["checks"] if c["id"] == cid)


def test_trading_series_with_idle_zeros_is_not_flagged() -> None:
    for idle in (0.5, 0.6, 0.7):
        r = _trading(idle)
        assert abs(rc.idle_share(r) - idle) < 0.05
        assert rc.zero_kink(r)["status"] == "pass"
        assert rc.round_numbers(r)["status"] == "pass"


def test_zeros_were_the_false_positive_before() -> None:
    # same data with zeros counted (what the old code did) trips both checks: proves the test would have caught the bug
    r = _trading(0.6)
    mu, sd = r.mean(), r.std(ddof=1)
    w = 0.25 * sd
    assert np.sum((r >= 0) & (r < w)) > 3 * np.sum((r >= -w) & (r < 0))
    k = r / 0.0005
    assert np.mean(np.abs(k - np.round(k)) < 1e-9) > 0.5
    assert mu == mu


def test_idle_share_reported_in_verify() -> None:
    r = _trading(0.6)
    rep = verify_returns(pd.Series(r, pd.date_range("2020-01-01", periods=r.size, freq="D")))
    row = next(c for c in rep["checks"] if c["id"] == "idle_share")
    assert row["status"] == "info" and 0.55 < row["details"]["idle_share"] < 0.65
    assert "periods in the market only" in row["summary"]
    assert _status(rep, "zero_kink") == "pass" and _status(rep, "round_numbers") == "pass"


def test_no_idle_row_without_zeros() -> None:
    rep = verify_returns(demo_returns(0)["honest"])
    assert not [c for c in rep["checks"] if c["id"] == "idle_share"]


def test_small_idle_share_is_listed_but_zeros_stay_in() -> None:
    r = _trading(0.05)
    rep = verify_returns(pd.Series(r, pd.date_range("2020-01-01", periods=r.size, freq="D")))
    row = next(c for c in rep["checks"] if c["id"] == "idle_share")
    assert "periods in the market only" not in row["summary"]
    assert rc.active_returns(r)[0].size == r.size


def test_boundary_at_threshold() -> None:
    r = np.concatenate([np.zeros(20), np.random.default_rng(1).normal(0, 0.01, 80)])
    assert rc.idle_share(r) == rc.IDLE_EXCLUDE
    assert rc.active_returns(r)[0].size == 80
    below = np.concatenate([np.zeros(19), np.random.default_rng(1).normal(0, 0.01, 81)])
    assert rc.active_returns(below)[0].size == 100


def test_rounded_fund_returns_still_flagged_with_idle_periods() -> None:
    rng = np.random.default_rng(1)
    active = np.round(rng.normal(0.007, 0.03, 120) / 0.0005) * 0.0005 + rng.normal(0, 1e-7, 120) * (rng.random(120) < 0.3)
    active = np.where(active == 0, 0.0005, active)
    r = np.concatenate([active, np.zeros(120)])  # half the record flat
    row = rc.round_numbers(r)
    assert row["status"] == "warn" and row["details"]["n_used"] == 120


def test_fund_hidden_losses_floored_at_zero_still_flagged() -> None:
    rng = np.random.default_rng(0)
    r = rng.normal(0.010, 0.012, 120)
    r[(r < 0) & (r > -0.004)] = 0.0  # small losses reported as exactly 0.00
    assert 0 < rc.idle_share(r) < rc.IDLE_EXCLUDE
    assert rc.zero_kink(r)["status"] == "warn"


def test_demo_too_good_trap_unchanged() -> None:
    assert rc.zero_kink(demo_returns(0)["too_good"].to_numpy())["status"] == "warn"


def test_all_idle_and_tiny_active_skip() -> None:
    assert rc.round_numbers(np.zeros(50))["status"] == "skip"
    one = np.zeros(50)
    one[0] = 0.01
    assert rc.zero_kink(one)["status"] == "skip"
    assert rc.zero_kink(np.concatenate([np.zeros(30), [0.01, 0.01]]))["status"] == "skip"  # zero volatility among active
