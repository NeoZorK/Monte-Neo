"""White's Reality Check and Hansen's SPA for parameter searches."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import verify_grid
from monte_neo.verify.reality import reality_check, reality_row


def _noise(models: int, bars: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal((models, bars)) * 0.01


def test_pure_noise_is_not_significant_on_average() -> None:
    p = [reality_check(_noise(40, 1500, seed))["p_spa"] for seed in range(20)]
    assert np.mean(p) > 0.3
    assert np.mean(np.array(p) < 0.05) <= 0.2  # about 5% expected; the bootstrap has real noise


def test_a_real_edge_among_noise_is_found() -> None:
    r = _noise(40, 1500, 1)
    r[7] += 0.0012
    info = reality_check(r)
    assert info["p_spa"] < 0.02 and info["p_reality_check"] < 0.05
    assert info["best_model"] == 7


def test_spa_is_not_diluted_by_bad_models_but_the_reality_check_is() -> None:
    r = _noise(40, 1500, 2)
    r[:30] *= 4.0
    r[:30] -= 0.001  # many high-variance losers
    r[35] += 0.0010
    info = reality_check(r)
    assert info["p_spa"] < 0.05
    assert info["p_reality_check"] > 0.5
    assert info["best_model"] == 35


def test_a_very_weak_edge_among_many_models_is_not_significant() -> None:
    r = _noise(40, 1500, 1)
    r[7] += 0.0003  # t of about 1.2: less than the best of 40 noise models usually shows
    assert reality_check(r)["p_spa"] > 0.1


def test_models_that_never_trade_are_ignored() -> None:
    r = _noise(5, 1500, 3)
    r[2] = 0.0
    info = reality_check(r)
    assert info["models"] == 5 and info["live_models"] == 4


def test_result_is_reproducible_and_non_finite_values_are_zero() -> None:
    r = _noise(10, 800, 4)
    r[3, 5] = np.nan
    assert reality_check(r) == reality_check(r)


@pytest.mark.parametrize("shape", [(1, 1500), (10, 50), (3,), (2, 3, 4)])
def test_too_little_data_gives_nothing(shape: tuple[int, ...]) -> None:
    assert reality_check(np.zeros(shape) + np.random.default_rng(0).standard_normal(shape)) == {}
    assert reality_row({})["status"] == "skip"


def test_a_search_over_a_random_walk_warns(tmp_path) -> None:
    df = synthetic_ohlcv(1500, seed=2)
    strategy = tmp_path / "s.py"
    strategy.write_text("import numpy as np\n\ndef signal(df, fast=10, slow=40):\n    c = df['close']\n    return np.sign(c.rolling(fast).mean() - c.rolling(slow).mean()).fillna(0).to_numpy()\n")
    report = verify_grid(df, {"fast": [5, 10, 20], "slow": [30, 60, 120]}, strategy=str(strategy))
    row = next(c for c in report["checks"] if c["id"] == "reality_check")
    assert row["category"] == "statistics" and row["status"] in ("pass", "warn")
    assert report["grid"]["reality"]["models"] == 9
    assert 0.0 < report["grid"]["reality"]["p_spa"] <= 1.0


def test_row_wording() -> None:
    warn = reality_row({"p_spa": 0.4, "p_reality_check": 0.5, "models": 12})
    ok = reality_row({"p_spa": 0.01, "p_reality_check": 0.02, "models": 12})
    assert warn["status"] == "warn" and "luck" in warn["summary"]
    assert ok["status"] == "pass" and "12" in ok["summary"]
