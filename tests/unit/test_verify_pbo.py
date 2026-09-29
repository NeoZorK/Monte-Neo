"""Probability of Backtest Overfitting (CSCV) and its use in verify_grid."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "traps"))
from trap_data import planted_momentum_ohlcv  # noqa: E402

from monte_neo.backtest import synthetic_ohlcv  # noqa: E402
from monte_neo.verify import model_from_costs, verify_grid  # noqa: E402
from monte_neo.verify.checks import NEXT_ACTIONS  # noqa: E402
from monte_neo.verify.pbo import pbo_cscv, pbo_row  # noqa: E402

TRAPS = Path(__file__).parents[1] / "traps" / "strategies"


def test_real_edge_has_low_pbo_and_pure_noise_does_not() -> None:
    """PBO of one noise draw is itself noisy, so compare averages over several draws."""
    rng = np.random.default_rng(1)
    slope = np.linspace(0.0005, 0.003, 40)[:, None]  # graded, strong edges: the ranking is stable
    edge = [pbo_cscv(rng.normal(0, 0.01, (40, 3200)) + slope) for _ in range(8)]
    noise = [pbo_cscv(rng.normal(0, 0.01, (40, 3200))) for _ in range(8)]
    good, bad = np.mean([e["pbo"] for e in edge]), np.mean([n["pbo"] for n in noise])
    assert good < 0.1 and 0.25 < bad < 0.65 and bad > good + 0.15
    assert np.mean([e["prob_loss"] for e in edge]) < np.mean([n["prob_loss"] for n in noise])
    assert np.mean([e["median_logit"] for e in edge]) > 0


def test_structure_and_determinism() -> None:
    r = np.random.default_rng(2).normal(0, 0.01, (12, 800))
    info = pbo_cscv(r)
    assert info["splits"] == 12870 and info["slices"] == 16 and info["combinations"] == 12
    assert sum(info["logit_hist"]["counts"]) == 12870 and len(info["logit_hist"]["counts"]) == 21
    assert pbo_cscv(r) == info and pbo_cscv(r, slices=8)["splits"] == 70
    assert pbo_cscv(np.asarray(r.tolist())) == info  # any array-like


def test_the_winner_is_not_changed_by_bars_beyond_whole_slices() -> None:
    """Bars that do not fill a slice are dropped, not spread: the result depends on the used bars only."""
    r = np.random.default_rng(3).normal(0, 0.01, (10, 810))
    assert pbo_cscv(r) == pbo_cscv(r[:, :800])


def test_cannot_be_computed() -> None:
    rng = np.random.default_rng(4)
    assert pbo_cscv(rng.normal(size=(3, 800))) == {}  # too few combinations
    assert pbo_cscv(rng.normal(size=(10, 40))) == {}  # too few bars
    assert pbo_cscv(rng.normal(size=(10,))) == {}
    assert pbo_cscv(rng.normal(size=(10, 800)), slices=7) == {}
    assert pbo_cscv(rng.normal(size=(10, 800)), slices=0) == {}


def test_non_finite_bars_are_ignored_and_ties_are_neutral() -> None:
    r = np.random.default_rng(5).normal(0, 0.01, (8, 640))
    r[2, 10] = np.nan
    r[3, 20] = np.inf
    assert 0.0 <= pbo_cscv(r)["pbo"] <= 1.0
    same = np.zeros((6, 640))
    assert 0.0 <= pbo_cscv(same)["pbo"] <= 1.0  # identical combinations: every rank is a tie


def test_row_statuses() -> None:
    assert pbo_row({})["status"] == "skip"
    base = {"pbo": 0.2, "splits": 12870, "prob_loss": 0.1}
    assert pbo_row(base)["status"] == "pass"
    warn = pbo_row({**base, "pbo": 0.62, "prob_loss": 0.55})
    assert warn["status"] == "warn" and "0.620" in warn["summary"] and "55%" in warn["summary"]
    assert "pbo" in NEXT_ACTIONS


def test_grid_reports_pbo_for_a_planted_edge_and_a_random_walk() -> None:
    hourly = planted_momentum_ohlcv()
    model = model_from_costs(commission_bps=1.0, slippage_bps=1.0, n_bars=len(hourly))
    planted = verify_grid(hourly, {"lookback": [1, 2, 3, 5, 8]}, strategy=TRAPS / "momentum_params.py", model=model)
    row = next(c for c in planted["checks"] if c["id"] == "pbo")
    assert row["status"] == "pass" and planted["grid"]["pbo"]["pbo"] < 0.25
    walk = verify_grid(synthetic_ohlcv(3000, seed=1), {"fast": [5, 10, 20, 40], "slow": [50, 80, 120, 200]}, strategy=TRAPS / "sma_params.py")
    assert next(c for c in walk["checks"] if c["id"] == "pbo")["details"]["combinations"] == 16
    assert len(json.dumps(walk["grid"]["pbo"])) < 600  # small enough to keep in every certificate


def test_a_single_combination_grid_skips_pbo() -> None:
    df = synthetic_ohlcv(1000, seed=2)
    report = verify_grid(df, {"lookback": [5]}, signal_fn=lambda d, lookback=5: (d["close"] > d["close"].shift(lookback)).astype(int).to_numpy())
    assert next(c for c in report["checks"] if c["id"] == "pbo")["status"] == "skip"
    assert report["grid"]["pbo"] == {}


def test_grid_certificate_records_pbo_and_the_number_of_trials() -> None:
    df = synthetic_ohlcv(1500, seed=7)
    report = verify_grid(df, {"fast": [5, 10], "slow": [30, 60]}, strategy=TRAPS / "sma_params.py")
    assert report["reproducibility"]["n_trials"] == 4 and report["grid"]["pbo"]["combinations"] == 4
