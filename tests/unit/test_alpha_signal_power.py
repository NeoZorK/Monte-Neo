"""Family A checks: signal power."""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from monte_neo.alpha import ALPHA_SCHEMA_ID, build_panel, demo_panel, validate_alpha
from monte_neo.alpha._core import ic_series, newey_west_t
from monte_neo.alpha.signal_power import check_long_short_legs, check_quantile_monotonicity, check_signal_placebo


def _by_id(report: dict) -> dict:
    return {c["id"]: c for c in report["checks"]}


def _panel_from_returns(ret: np.ndarray, score: np.ndarray):
    """Long tables whose day-t score faces the day t->t+1 return ``ret[t]``."""
    t, n = ret.shape
    close = 100 * np.cumprod(1 + np.vstack([np.zeros((1, n)), ret[:-1]]), axis=0)
    dates = pd.bdate_range("2020-01-01", periods=t)
    syms = [f"S{i}" for i in range(n)]
    px = pd.DataFrame({"timestamp": np.repeat(dates, n), "symbol": np.tile(syms, t), "close": close.ravel()})
    sc = pd.DataFrame({"timestamp": np.repeat(dates, n), "symbol": np.tile(syms, t), "score": score.ravel()})
    return build_panel(px, sc)


def test_real_signal_is_significant_and_beats_placebo() -> None:
    prices, real, _ = demo_panel(0)
    c = _by_id(validate_alpha(prices, real))
    assert c["ic"]["status"] == "info" and c["ic"]["details"]["t_stat"] >= 2
    assert 0.02 < c["ic"]["details"]["mean_ic"] < 0.08
    assert c["signal_placebo"]["status"] == "pass"
    assert c["quantile_monotonicity"]["status"] == "pass"


def test_noise_signal_warns_and_fails_placebo() -> None:
    prices, _, noise = demo_panel(2)
    c = _by_id(validate_alpha(prices, noise))
    assert c["ic"]["status"] == "warn"
    assert c["signal_placebo"]["status"] == "fail"


def test_report_schema_and_json() -> None:
    import json

    prices, real, _ = demo_panel(0, 12, 120)
    rep = validate_alpha(prices, real, claimed_ir=0.5, placebos=20)
    json.dumps(rep, allow_nan=False)
    assert rep["schema"] == ALPHA_SCHEMA_ID == "alpha-report/1"
    assert {"verdict", "checks", "metrics", "next_actions", "reproducibility", "disclaimer"} <= rep.keys()
    assert len(rep["reproducibility"]["data_sha256"]["prices"]) == 64
    assert _by_id(rep)["breadth_consistency"]["status"] in ("pass", "warn")


def test_deterministic_with_seed() -> None:
    prices, real, _ = demo_panel(0, 15, 150)
    assert validate_alpha(prices, real, seed=3, placebos=30) == validate_alpha(prices, real, seed=3, placebos=30)


def test_ic_perfect_and_newey_west() -> None:
    rng = np.random.default_rng(0)
    r = rng.standard_normal((50, 10))
    assert np.allclose(ic_series(r, r), 1.0)
    assert np.allclose(ic_series(r, -r), -1.0)
    x = np.tile([1.0, -1.0], 100) + 0.1
    _, _, t0 = newey_west_t(x, 0)
    _, _, t5 = newey_west_t(x, 5)
    assert t5 != t0


def test_monotone_vs_one_extreme() -> None:
    rng = np.random.default_rng(1)
    t, n = 300, 50
    score = rng.standard_normal((t, n))
    rank = score.argsort(1).argsort(1) / (n - 1)
    noise = 0.01 * rng.standard_normal((t, n))
    mono = _panel_from_returns(0.004 * (rank - 0.5) + noise, score)
    assert check_quantile_monotonicity(mono, mono.forward_returns(1))["status"] == "pass"
    one = _panel_from_returns(0.01 * (rank < 0.2) * -1.0 + noise, score)  # only the bottom bucket moves
    res = check_quantile_monotonicity(one, one.forward_returns(1))
    assert res["status"] == "warn"


def test_short_leg_share() -> None:
    rng = np.random.default_rng(2)
    t, n = 300, 50
    score = rng.standard_normal((t, n))
    rank = score.argsort(1).argsort(1) / (n - 1)
    noise = 0.005 * rng.standard_normal((t, n))
    short_only = _panel_from_returns(-0.01 * (rank < 0.2) + noise, score)
    c = check_long_short_legs(short_only, short_only.forward_returns(1))
    assert c["status"] == "warn" and c["details"]["short_share"] > 0.7
    long_only = _panel_from_returns(0.01 * (rank >= 0.8) + noise, score)
    assert check_long_short_legs(long_only, long_only.forward_returns(1))["status"] == "pass"


def test_breadth_claim_too_high_warns() -> None:
    prices, real, _ = demo_panel(0, 20, 200)
    c = _by_id(validate_alpha(prices, real, claimed_ir=50.0, placebos=20))
    assert c["breadth_consistency"]["status"] == "warn"
    assert _by_id(validate_alpha(prices, real, placebos=20))["breadth_consistency"]["status"] == "skip"


def test_placebo_is_fast() -> None:
    prices, real, _ = demo_panel(0, 100, 1000)
    panel = build_panel(prices, real)
    start = time.perf_counter()
    check_signal_placebo(panel, panel.forward_returns(1))
    assert time.perf_counter() - start < 2.0


def test_ic_decay_reports_best_horizon() -> None:
    prices, real, _ = demo_panel(0)
    d = _by_id(validate_alpha(prices, real, placebos=20))["ic_decay"]["details"]
    assert d["best_horizon"] == 1 and len(d["ic"]) == 20
