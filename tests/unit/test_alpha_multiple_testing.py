"""Family F: statistics across all attempts."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from monte_neo.alpha.multiple_testing import (
    bhy_qvalues,
    drawdown_plausibility,
    fdr_across_ledger,
    haircut_sharpe,
    hlz_hurdle,
    min_backtest_length,
    romano_wolf,
    run_multiple_testing,
    t_stats_from_ledger,
)


def test_hlz_statuses() -> None:
    rng = np.random.default_rng(0)
    assert hlz_hurdle(rng.normal(0.003, 0.01, 2000))["status"] == "pass"
    assert hlz_hurdle(rng.normal(0.0, 0.01, 2000) + 0.0)["status"] in {"info", "warn"}
    noise = np.random.default_rng(3).normal(0.0, 0.01, 500)
    assert hlz_hurdle(noise - noise.mean() + 0.0001)["status"] == "info"
    mid = np.random.default_rng(4).normal(0, 0.01, 1000)
    mid = (mid - mid.mean()) / mid.std() * 0.01 + 0.01 * 2.5 / math.sqrt(1000)
    assert hlz_hurdle(mid)["status"] == "warn"


def test_bhy_q_monotone_and_bounded() -> None:
    p = np.array([0.001, 0.01, 0.02, 0.04, 0.2, 0.7])
    q = bhy_qvalues(p)
    assert np.all(np.diff(q) >= 0)
    assert np.all(q >= p) and q.max() <= 1.0


def test_fdr_warns_for_weak_current() -> None:
    row = fdr_across_ledger([4.5, 4.0, 3.8, 0.5, 1.0, 0.3, 1.2], current_index=6)
    assert row["status"] == "warn"
    assert fdr_across_ledger([4.5, 0.2, 0.5, 0.1, 0.3], current_index=0)["status"] == "pass"


def test_t_stats_from_ledger() -> None:
    entries = [
        {"data": "d1", "variant": "a", "sharpe": 1.0},
        {"data": "d1", "variant": "b", "sharpe": 2.0},
        {"data": "d2", "variant": "c", "sharpe": 5.0},
        {"data": "d1", "variant": "a", "sharpe": 1.5},
    ]
    t = t_stats_from_ledger(entries, "d1", 252, 252.0)
    assert np.allclose(t, [1.5, 2.0])


def test_romano_wolf_finds_planted_variant() -> None:
    rng = np.random.default_rng(1)
    x = rng.normal(0, 0.01, (1000, 20))
    x[:, 7] += 0.004
    row = romano_wolf(x, seed=0)
    assert row["details"]["significant"] == [7]
    assert romano_wolf(x, seed=0) == row


def test_romano_wolf_nothing_in_noise() -> None:
    x = np.random.default_rng(2).normal(0, 0.01, (800, 15))
    assert romano_wolf(x)["details"]["significant"] == []


def test_min_btl_math_and_statuses() -> None:
    row = min_backtest_length(1.0, 100, 8.0)
    assert math.isclose(row["details"]["years_needed"], 2 * math.log(100))
    assert row["status"] == "warn"
    assert min_backtest_length(1.0, 100, 3.0)["status"] == "fail"
    assert min_backtest_length(1.0, 5, 3.0)["status"] == "warn"
    assert min_backtest_length(2.0, 10, 5.0)["status"] == "pass"
    assert min_backtest_length(1.0, 1, 1.0)["status"] == "pass"


def test_drawdown_too_smooth_warns() -> None:
    rng = np.random.default_rng(0)
    noisy = rng.normal(0.0004, 0.01, 1500)
    # alternating gains and losses: tiny drawdowns for its volatility
    r = np.where(np.arange(1500) % 2 == 0, 0.02, -0.0185)
    assert drawdown_plausibility(r, 252.0)["status"] == "warn"
    assert drawdown_plausibility(noisy, 252.0)["status"] == "pass"


def test_haircut_grows_with_trials() -> None:
    h10 = haircut_sharpe(1.5, 1000, 10, 252.0)["details"]["bonferroni"]["haircut_pct"]
    h1000 = haircut_sharpe(1.5, 1000, 1000, 252.0)["details"]["bonferroni"]["haircut_pct"]
    h1 = haircut_sharpe(1.5, 1000, 1, 252.0)["details"]["bonferroni"]["haircut_pct"]
    assert h1 < 1e-6 < h10 < h1000 <= 100.0
    holm = haircut_sharpe(1.5, 1000, 50, 252.0)["details"]["holm_sidak"]["haircut_pct"]
    assert 0 < holm <= h1000


def test_run_multiple_testing_ids() -> None:
    idx = pd.bdate_range("2015-01-01", periods=2000)
    r = np.random.default_rng(0).normal(0.0005, 0.01, 2000)
    ids = [x["id"] for x in run_multiple_testing(r, 252.0, 20, timestamps=idx)]
    assert ids == ["hlz_hurdle", "min_backtest_length", "drawdown_plausibility", "haircut_sharpe"]
    ids2 = [x["id"] for x in run_multiple_testing(r, 252.0, 20, t_stats=[3.0, 1.0, 2.0])]
    assert "fdr_across_ledger" in ids2
