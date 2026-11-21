"""Sequential forward test: valid under daily peeking (false passes stay rare), and decisive on large effects."""

from __future__ import annotations

import math
import random

from monte_neo.deploy.sequential import days_needed, evaluate, standardise


def _path(sharpe: float, n: int, rng: random.Random, vol: float = 0.02) -> list[float]:
    mu = sharpe * vol / math.sqrt(365)
    return [mu + vol * rng.gauss(0, 1) for _ in range(n)]


def test_null_records_rarely_pass_even_with_daily_peeking() -> None:
    rng = random.Random(7)
    passes = sum(evaluate(_path(0.0, 182, rng))["decision"] == "PASS" for _ in range(300))
    assert passes / 300 <= 0.02  # alpha 0.05 is the ceiling; the bets are conservative


def test_a_very_large_edge_passes_and_a_collapse_fails_early() -> None:
    rng = random.Random(11)
    strong = [evaluate(_path(8.0, 182, rng))["decision"] for _ in range(60)]
    assert strong.count("PASS") / 60 >= 0.8
    broken = [evaluate(_path(-6.0, 182, rng), target_sharpe=2.0)["decision"] for _ in range(60)]
    assert broken.count("FAIL_EARLY") / 60 >= 0.8


def test_more_candidates_need_more_evidence() -> None:
    rng = random.Random(3)
    r = _path(5.0, 182, rng)
    one, many = evaluate(r, n_trials=1), evaluate(r, n_trials=100)
    assert many["threshold"] == 100 * one["threshold"] and many["e_edge"] == one["e_edge"]


def test_minimum_days_and_honest_horizon() -> None:
    rng = random.Random(5)
    r = evaluate(_path(30.0, 40, rng))
    assert r["decision"] == "CONTINUE"  # even a huge edge cannot pass before min_pass_days (56)
    assert days_needed(1.0) > 2000 and days_needed(3.0) < 300 and days_needed(-1.0) is None
    assert len(standardise([0.01] * 5)) == 0  # the warm-up days are never bet on
