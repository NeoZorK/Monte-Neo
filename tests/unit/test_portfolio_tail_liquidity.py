"""Tail dependence, correlation-breakdown stress and liquidity stress."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.verify.liquidity_stress import liquidity_stress, liquidity_stress_row
from monte_neo.verify.portfolio_tail import (
    correlation_stress_row,
    stressed_cvar,
    tail_dependence,
    tail_dependence_row,
)

RNG = np.random.default_rng(11)
N = 3000


def _independent(k: int = 4) -> np.ndarray:
    return RNG.normal(0, 0.01, (k, N))


def _crash_together(k: int = 4) -> np.ndarray:
    m = RNG.normal(0, 0.01, (k, N))
    crash = RNG.random(N) < 0.03
    m[:, crash] -= 0.05  # a common shock in 3 % of the bars, otherwise independent
    return m


def test_independent_series_have_tail_dependence_near_q() -> None:
    td = tail_dependence(_independent())
    assert td["lower"] == pytest.approx(0.05, abs=0.04)
    assert tail_dependence_row(td)["status"] == "pass"


def test_common_crash_shows_up_as_tail_dependence_that_correlation_hides() -> None:
    m = _crash_together()
    td = tail_dependence(m)
    assert td["lower"] > 0.3 and td["upper"] < 0.2  # asymmetric: only the lower tail is joint
    row = tail_dependence_row(td)
    assert row["status"] == "warn" and "fall together" in row["summary"]


def test_clones_are_fully_dependent_and_inputs_are_validated() -> None:
    x = RNG.normal(0, 0.01, N)
    assert tail_dependence(np.vstack([x, x]))["lower"] == pytest.approx(1.0)
    with pytest.raises(ValueError):
        tail_dependence(np.zeros((1, 50)))
    with pytest.raises(ValueError):
        tail_dependence(_independent(), q=0.7)
    assert tail_dependence_row(tail_dependence(RNG.normal(0, 1, (2, 20)), q=0.1))["status"] == "skip"  # 2 tail bars < 5


def test_stress_raises_es_for_diversified_book_and_never_lowers_it() -> None:
    m = _independent(5)
    r = stressed_cvar(m, stress_corr=0.9)
    assert r["ratio"] > 1.5 and correlation_stress_row(r)["status"] == "warn"
    clones = np.vstack([m[0]] * 3)
    assert stressed_cvar(clones, stress_corr=0.1)["ratio"] == pytest.approx(1.0)  # already fully correlated
    assert correlation_stress_row({"ratio": None})["status"] == "skip"
    mild = stressed_cvar(_independent(2), stress_corr=0.1)
    assert correlation_stress_row(mild)["status"] == "pass"


def _book(turn: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    close = 100 * np.cumprod(1 + RNG.normal(0.0008, 0.01, 800))
    target = np.where((np.arange(800) // turn) % 2 == 0, 1.0, 0.0)
    return target, close, np.full(800, 5e6)


def test_liquidity_stress_warns_for_a_heavy_trader_not_for_a_patient_one() -> None:
    t, c, v = _book(2)  # trades every second bar
    heavy = liquidity_stress(t, c, v, capital=5e6, fee_bps=1.0)
    patient_t, pc, pv = _book(200)
    calm = liquidity_stress(patient_t, pc, pv, capital=1e5, fee_bps=1.0)
    assert heavy["stressed_return"] < heavy["normal_return"]
    assert liquidity_stress_row(calm)["status"] in ("pass", "skip")
    assert liquidity_stress_row({**heavy, "normal_return": 0.2, "stressed_return": -0.05})["status"] == "warn"
    assert liquidity_stress_row({**heavy, "normal_return": 0.2, "stressed_return": 0.18})["status"] == "pass"
    assert liquidity_stress_row({**heavy, "normal_return": -0.1})["status"] == "skip"


def test_liquidity_stress_validates_inputs() -> None:
    t, c, v = _book(10)
    for bad in ({"volume_keep": 0.0}, {"impact_mult": 0.5}, {"spread_bps": -1.0}):
        with pytest.raises(ValueError):
            liquidity_stress(t, c, v, capital=1e5, **bad)


def test_portfolio_risk_carries_the_tail_rows() -> None:
    from monte_neo.verify.portfolio_risk import portfolio_risk

    rep = portfolio_risk(_crash_together(3), ["a", "b", "c"])
    ids = {c["id"]: c["status"] for c in rep["checks"]}
    assert ids["tail_dependence"] == "warn" and "correlation_breakdown_stress" in ids
