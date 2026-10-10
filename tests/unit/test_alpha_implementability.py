"""Synthetic tests for the family D implementability checks."""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.alpha.implementability import (
    capacity_curve,
    market_impact,
    participation_limit,
    short_feasibility,
)
from monte_neo.alpha.implementability_timing import (
    execution_price_sensitivity,
    rebalance_timing_luck,
    tranche_weights,
    turnover_vs_decay,
)

T, N = 400, 3
IDX = pd.bdate_range("2020-01-01", periods=T)


def _market(seed: int = 0, vol_units: float = 1e4) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0, 0.01, (T, N))
    close = 100.0 * np.cumprod(1.0 + ret, axis=0)
    volume = np.full((T, N), vol_units)
    weights = np.zeros((T, N))
    weights[:-1] = np.sign(ret[1:]) / N  # perfect foresight: positive gross, high turnover
    return weights, close, volume


def test_market_impact_fails_for_huge_aum_and_passes_small() -> None:
    w, c, v = _market()
    big = market_impact(w, c, v, IDX, aum=1e10)
    small = market_impact(w, c, v, IDX, aum=1e3)
    assert big["status"] == "fail"
    assert small["status"] == "pass"
    assert big["details"]["net_annual_return"] < small["details"]["net_annual_return"]


def test_market_impact_warns_when_impact_eats_half() -> None:
    w, c, v = _market()
    lo, hi = 1e3, 1e10
    for _ in range(60):  # bisect AUM where impact is ~70 % of gross
        mid = (lo * hi) ** 0.5
        share = market_impact(w, c, v, IDX, aum=mid, commission_bps=0.0)["details"]["impact_share_of_gross"]
        lo, hi = (mid, hi) if share < 0.7 else (lo, mid)
    assert market_impact(w, c, v, IDX, aum=lo, commission_bps=0.0)["status"] == "warn"


def test_no_volume_skips() -> None:
    w, c, _ = _market()
    assert market_impact(w, c, None, IDX, aum=1e6)["status"] == "skip"
    assert capacity_curve(w, c, None, IDX)["status"] == "skip"
    assert participation_limit(w, c, None, 1e6)["status"] == "skip"
    assert short_feasibility(w, c, None, IDX)["status"] == "skip"


def test_capacity_curve_monotone() -> None:
    w, c, v = _market()
    row = capacity_curve(w, c, v, IDX)
    curve = row["details"]["curve"]
    assert len(curve) == 15
    sharpes = [p["net_sharpe"] for p in curve]
    assert all(b <= a + 1e-9 for a, b in zip(sharpes, sharpes[1:], strict=False))
    assert row["status"] == "info"
    assert row["details"]["aum_zero"] is not None


def test_participation_thresholds() -> None:
    w, c, v = _market()
    value = float(np.median(c * v))
    traded_mean = float(np.abs(np.diff(w, axis=0)).mean())
    ok = participation_limit(w, c, v, aum=0.01 * value / traded_mean)
    warn = participation_limit(w, c, v, aum=0.12 * value / traded_mean * 2)
    fail = participation_limit(w, c, v, aum=1e5 * value)
    assert ok["status"] == "pass"
    assert warn["status"] in {"warn", "fail"}
    assert fail["status"] == "fail"
    assert fail["details"]["p95"] > ok["details"]["p95"]
    lim = 0.05
    p95 = warn["details"]["p95"]
    assert warn["status"] == ("fail" if p95 > 4 * lim else "warn")


def test_short_in_illiquid_names_warns() -> None:
    rng = np.random.default_rng(1)
    n = 10
    close = 100.0 * np.cumprod(1.0 + rng.normal(0, 0.01, (T, n)), axis=0)
    volume = np.tile(np.linspace(1e6, 1e3, n), (T, 1))  # last names illiquid
    short_illiquid = np.zeros((T, n))
    short_illiquid[:, -2:] = -0.5
    short_liquid = np.zeros((T, n))
    short_liquid[:, :2] = -0.5
    bad = short_feasibility(short_illiquid, close, volume, IDX)
    good = short_feasibility(short_liquid, close, volume, IDX, borrow_bps_per_year=1.0)
    assert bad["status"] == "warn" and bad["details"]["illiquid_short_share"] > 0.3
    assert good["details"]["illiquid_short_share"] < 0.3


def test_turnover_vs_decay_message() -> None:
    w = np.zeros((100, 1))
    w[::3] = 1.0
    row = turnover_vs_decay(np.repeat(np.sign(np.sin(np.arange(100) / 1.0))[:, None], 1, axis=1), half_life_bars=20)
    assert row["status"] == "info" and "more than the signal needs" in row["summary"]
    assert turnover_vs_decay(w)["details"]["half_life_bars"] is None


def _cycle_market() -> tuple[np.ndarray, np.ndarray]:
    t = np.arange(1050)
    ret = np.where(t % 21 == 1, 0.05, 0.0)[:, None]
    close = 100.0 * np.cumprod(1.0 + ret, axis=0)
    return close, t


def test_rebalance_timing_luck_planted_jump_warns_and_smooth_passes() -> None:
    close, t = _cycle_market()
    idx = pd.bdate_range("2018-01-01", periods=len(t))
    luck_w = np.where(t % 21 == 0, 1.0, 0.0)[:, None]
    row = rebalance_timing_luck(luck_w, close, idx, k=21)
    assert row["status"] == "warn" and len(row["details"]["values"]) == 21
    rng = np.random.default_rng(3)
    smooth_close = 100.0 * np.cumprod(1.0 + 0.0008 + rng.normal(0, 0.005, (len(t), 1)), axis=0)
    smooth = rebalance_timing_luck(np.ones((len(t), 1)), smooth_close, idx, k=21)
    assert smooth["status"] == "pass"


def test_tranche_weights_average_of_sleeves() -> None:
    w = np.arange(60, dtype=float).reshape(-1, 1)
    out = tranche_weights(w, 4, 4)
    assert out.shape == w.shape
    assert np.isclose(out[40, 0], np.mean([40, 39, 38, 37]))
    assert np.allclose(tranche_weights(w, 4, 1)[8:], w[8:] - (np.arange(8, 60) % 4)[:, None])


def test_execution_price_sign_flip_warns() -> None:
    n = 300
    d = np.where(np.arange(n) % 2 == 0, 0.01, -0.01)
    close = np.empty(n)
    open_ = np.empty(n)
    prev = 100.0
    for i in range(n):
        open_[i] = prev
        close[i] = prev * (1.0 + d[i])
        prev = close[i]
    w = np.where(np.arange(n) % 2 == 0, 1.0, 0.0)[:, None]
    idx = pd.bdate_range("2020-01-01", periods=n)
    row = execution_price_sensitivity(w, open_[:, None], close[:, None], idx)
    assert row["status"] == "warn" and row["details"]["sign_change"]
    smooth_close = 100.0 * np.cumprod(np.full((n, 1), 1.001), axis=0)
    smooth_open = np.vstack([[100.0], smooth_close[:-1]])
    flat = execution_price_sensitivity(np.ones((n, 1)), smooth_open, smooth_close, idx)
    assert flat["status"] == "pass"
