"""A6: statistics and method. Expectations come from formulas and from simulations with a known truth."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify import verify_strategy
from monte_neo.verify.confidence import bootstrap_ci, min_track_record_bars
from monte_neo.verify.pbo import pbo_cscv
from monte_neo.verify.reality import reality_check
from monte_neo.verify.stats import deflated_sharpe, infer_periods_per_year, lo_adjusted_sharpe, probabilistic_sharpe

# ---- annualisation ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("ppy", [12.0, 252.0, 365.0, 8760.0])
def test_the_annualized_sharpe_is_mean_over_std_times_root_periods(ppy: float) -> None:
    rng = np.random.default_rng(1)
    r = rng.normal(0.001, 0.01, 2000)
    out = deflated_sharpe(r, periods_per_year=ppy)
    assert out["sharpe_annualized"] == pytest.approx(r.mean() / r.std(ddof=1) * math.sqrt(ppy), rel=1e-9)


@pytest.mark.parametrize(
    "freq,periods,low,high",
    [("1D", 900, 360, 370), ("B", 1000, 248, 262), ("1h", 3000, 8600, 8800), ("15min", 4000, 34_000, 35_500)],
)
def test_periods_per_year_follow_the_calendar_of_the_stamps(freq: str, periods: int, low: float, high: float) -> None:
    stamps = pd.date_range("2022-01-03", periods=periods, freq=freq)
    assert low <= infer_periods_per_year(stamps) <= high


# ---- PSR, DSR, minimum track record -----------------------------------------------------------------------------------


def test_the_psr_of_a_zero_sharpe_is_one_half_and_grows_with_the_sample() -> None:
    assert probabilistic_sharpe(0.0, 500, 0.0, 3.0, 0.0) == pytest.approx(0.5)
    short, long = (probabilistic_sharpe(0.05, n, 0.0, 3.0, 0.0) for n in (100, 1000))
    assert 0.5 < short < long < 1.0


def test_fat_tails_and_negative_skew_lower_the_confidence() -> None:
    normal = probabilistic_sharpe(0.05, 500, 0.0, 3.0, 0.0)
    assert probabilistic_sharpe(0.05, 500, 0.0, 12.0, 0.0) < normal
    assert probabilistic_sharpe(0.05, 500, -1.5, 3.0, 0.0) < normal


def test_the_dsr_equals_the_psr_for_one_trial_and_falls_as_trials_grow() -> None:
    rng = np.random.default_rng(2)
    r = rng.normal(0.0012, 0.01, 1500)
    one = deflated_sharpe(r, n_trials=1)
    assert one["deflated_sharpe"] == pytest.approx(one["psr"])
    values = [deflated_sharpe(r, n_trials=n)["deflated_sharpe"] for n in (1, 5, 50, 500, 5000)]
    assert values == sorted(values, reverse=True) and values[-1] < values[0]


def test_the_best_of_many_noise_strategies_looks_real_until_the_trials_are_counted() -> None:
    rng = np.random.default_rng(3)
    fooled = deflated = 0
    runs = 40
    for _ in range(runs):
        mat = rng.normal(0.0, 0.01, (100, 750))
        sharpes = mat.mean(axis=1) / mat.std(axis=1, ddof=1)
        best = mat[int(np.argmax(sharpes))]
        fooled += deflated_sharpe(best, n_trials=1)["psr"] > 0.95
        deflated += deflated_sharpe(best, n_trials=100, trial_sharpes=sharpes)["deflated_sharpe"] > 0.95
    assert fooled >= runs * 0.6  # without counting, the winner of 100 usually passes a 95 % test
    assert deflated <= runs * 0.1  # with the count it almost never does


def test_the_minimum_track_record_matches_its_definition() -> None:
    sr = 0.06
    need = min_track_record_bars(sr, 0.0, 3.0)
    assert need is not None and probabilistic_sharpe(sr, math.ceil(need), 0.0, 3.0, 0.0) >= 0.95
    assert probabilistic_sharpe(sr, int(need * 0.8), 0.0, 3.0, 0.0) < 0.95
    flat = min_track_record_bars(sr, 0.0, 1.0)  # kurtosis 1 makes the variance factor exactly 1: the bars go with 1 / SR^2
    assert flat is not None and min_track_record_bars(sr / 2, 0.0, 1.0) == pytest.approx(1 + (flat - 1) * 4, rel=1e-9)
    assert min_track_record_bars(-0.1, 0.0, 3.0) is None and min_track_record_bars(0.02, 0.0, 3.0, sr_benchmark=0.05) is None


# ---- intervals -------------------------------------------------------------------------------------------------------


def test_the_bootstrap_interval_covers_the_true_sharpe_about_as_often_as_it_claims() -> None:
    rng = np.random.default_rng(4)
    mu, sd, ppy = 0.0008, 0.01, 252.0
    truth = mu / sd * math.sqrt(ppy)
    covered = 0
    runs = 60
    for _ in range(runs):
        r = rng.normal(mu, sd, 1500)
        lo, hi = bootstrap_ci(r, ppy, samples=300)["sharpe_annualized"]
        covered += lo <= truth <= hi
    assert covered >= runs * 0.82


# ---- selection across many models ------------------------------------------------------------------------------------


def test_reality_check_and_spa_rarely_fire_on_noise_and_usually_on_a_real_edge() -> None:
    rng = np.random.default_rng(5)
    noise_hits = edge_hits = 0
    runs = 120
    for _ in range(runs):
        noise = rng.normal(0.0, 0.01, (20, 600))
        noise_hits += reality_check(noise, samples=200)["p_reality_check"] < 0.05
        edge = noise.copy()
        edge[7] += 0.002
        edge_hits += reality_check(edge, samples=200)["p_spa"] < 0.05
    assert noise_hits <= runs * 0.12  # White's test has the size it claims (about 5 %); Hansen's SPA is a little liberal at about 7 %
    assert edge_hits >= runs * 0.7


def test_pbo_is_about_one_half_on_noise_and_small_when_one_model_is_better() -> None:
    rng = np.random.default_rng(6)
    noise = rng.normal(0.0, 0.01, (16, 800))
    edge = noise.copy()
    edge[3] += 0.0015
    assert 0.25 <= pbo_cscv(noise)["pbo"] <= 0.75
    assert pbo_cscv(edge)["pbo"] < 0.2


# ---- serial correlation (smoothed returns) -----------------------------------------------------------------------------


def test_smoothing_inflates_the_naive_sharpe_and_the_lo_correction_takes_it_back() -> None:
    rng = np.random.default_rng(7)
    raw = rng.normal(0.0006, 0.01, 6000)
    smooth = np.convolve(raw, np.ones(5) / 5, mode="valid")
    plain = lo_adjusted_sharpe(raw, 252.0)
    marked = lo_adjusted_sharpe(smooth, 252.0)
    assert marked["naive"] > plain["naive"] * 1.8  # smoothing alone made the Sharpe look twice as good
    assert marked["adjusted"] == pytest.approx(plain["naive"], rel=0.25)  # the correction brings it back to the truth
    assert abs(plain["adjusted"] - plain["naive"]) / plain["naive"] < 0.08  # and leaves honest returns alone


def test_the_serial_correlation_row_is_information_and_never_moves_the_verdict() -> None:
    rng = np.random.default_rng(8)
    n = 1500
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    df = pd.DataFrame({"open": close, "high": close * 1.002, "low": close * 0.998, "close": close})
    pos = np.where((np.arange(n) // 25) % 2 == 0, 1, 0)
    report = verify_strategy(df, signals=pos)
    row = next(c for c in report["checks"] if c["id"] == "serial_correlation")
    assert row["status"] == "info" and {"naive", "adjusted", "rho1"} <= set(row["details"])
