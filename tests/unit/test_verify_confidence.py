"""Bootstrap intervals and the minimum track record length."""

from __future__ import annotations

import math

import numpy as np
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import verify_strategy
from monte_neo.verify.confidence import (
    block_length,
    bootstrap_ci,
    confidence_row,
    min_track_record_bars,
    track_record,
    track_record_row,
)
from monte_neo.verify.stats import deflated_sharpe, probabilistic_sharpe, sharpe_per_bar


def test_bootstrap_interval_covers_the_estimate_and_is_reproducible() -> None:
    rng = np.random.default_rng(3)
    r = rng.normal(0.0008, 0.01, 4000)
    ci = bootstrap_ci(r, 252.0)
    lo, hi = ci["sharpe_annualized"]
    point = sharpe_per_bar(r) * math.sqrt(252.0)
    assert lo < point < hi and hi - lo > 0.5
    assert ci["total_return"][0] < float(np.prod(1 + r) - 1) < ci["total_return"][1]
    assert ci["block_bars"] == block_length(4000) == 16 and ci["samples"] == 1000
    assert bootstrap_ci(r, 252.0) == ci  # fixed seed: same certificate every time


def test_interval_width_shrinks_with_more_data_and_tracks_the_sign() -> None:
    rng = np.random.default_rng(4)
    short, long_ = rng.normal(0.001, 0.01, 500), rng.normal(0.001, 0.01, 8000)
    w = lambda ci: ci["sharpe_annualized"][1] - ci["sharpe_annualized"][0]  # noqa: E731
    assert w(bootstrap_ci(long_, 252.0)) < w(bootstrap_ci(short, 252.0))
    noise = bootstrap_ci(rng.normal(0.0, 0.01, 3000), 252.0)
    assert noise["sharpe_annualized"][0] < 0 < noise["sharpe_annualized"][1] and 0.05 < noise["prob_sharpe_positive"] < 0.95
    losing = bootstrap_ci(rng.normal(-0.002, 0.01, 3000), 252.0)
    assert losing["prob_sharpe_positive"] == 0.0


def test_bootstrap_coverage_of_the_true_sharpe() -> None:
    """About 95% of intervals contain the true annualized Sharpe (loose bounds, 60 trials)."""
    true = 0.0005 / 0.01 * math.sqrt(252.0)
    hits = 0
    rng = np.random.default_rng(11)
    for _ in range(60):
        ci = bootstrap_ci(rng.normal(0.0005, 0.01, 1500), 252.0, samples=300)
        hits += ci["sharpe_annualized"][0] <= true <= ci["sharpe_annualized"][1]
    assert 47 <= hits <= 60  # 78% to 100%


def test_bootstrap_edge_cases() -> None:
    assert bootstrap_ci(np.zeros(30), 252.0) == {}
    assert bootstrap_ci(np.array([np.nan] * 100), 252.0) == {}
    flat = bootstrap_ci(np.zeros(500), 252.0)
    assert flat["sharpe_annualized"] == [0.0, 0.0] and flat["total_return"] == [0.0, 0.0]
    crash = bootstrap_ci(np.concatenate([np.full(200, 0.001), [-1.5]]), 252.0)  # a return below -100% must not produce NaN
    assert all(math.isfinite(v) for v in crash["total_return"])


def test_min_track_record_matches_the_probabilistic_sharpe() -> None:
    """At the minimum length the PSR against zero is exactly the confidence level."""
    sr, skew, kurt = 0.05, -0.4, 6.0
    n = min_track_record_bars(sr, skew, kurt)
    assert probabilistic_sharpe(sr, int(round(n)), skew, kurt, 0.0) == pytest.approx(0.95, abs=0.005)
    assert min_track_record_bars(0.0, 0.0, 3.0) is None and min_track_record_bars(-0.1, 0.0, 3.0) is None
    assert min_track_record_bars(math.nan, 0.0, 3.0) is None
    assert min_track_record_bars(0.05, 0.0, 3.0) < min_track_record_bars(0.02, 0.0, 3.0)
    assert min_track_record_bars(0.9, 5.0, 3.0) > 1  # a degenerate denominator is clamped, not negative


def test_track_record_and_rows() -> None:
    rng = np.random.default_rng(5)
    good = deflated_sharpe(rng.normal(0.001, 0.01, 800), periods_per_year=252.0)
    info = track_record(good, 252.0)
    assert info["have_bars"] == 800 and info["need_bars"] > 0 and info["need_years"] == pytest.approx(info["need_bars"] / 252, abs=0.01)
    row = track_record_row(info)
    assert row["status"] == "info" and "needs" in row["summary"]
    short = track_record_row({**info, "have_bars": 10, "need_bars": 5000, "need_years": 19.8})
    assert "not enough history yet" in short["summary"]
    losing = track_record(deflated_sharpe(rng.normal(-0.001, 0.01, 800)), 252.0)
    assert losing["need_bars"] is None and "not positive" in track_record_row(losing)["summary"]
    assert confidence_row({})["status"] == "skip"
    ci = confidence_row(bootstrap_ci(rng.normal(0.001, 0.01, 1000), 252.0))
    assert ci["status"] == "info" and "interval" in ci["summary"] and ci["details"]["samples"] == 1000


def test_checks_are_context_only_and_metrics_are_recorded() -> None:
    df = synthetic_ohlcv(1200, seed=6)
    sig = (df["close"] > df["close"].rolling(20).mean()).astype(int).to_numpy()
    report = verify_strategy(df, signals=sig)
    rows = {c["id"]: c for c in report["checks"]}
    assert rows["sharpe_confidence"]["status"] == "info" and rows["track_record"]["status"] == "info"
    lo, hi = report["metrics"]["sharpe_ci95"]
    assert lo <= report["metrics"]["sharpe_annualized"] <= hi
    assert "min_track_record_bars" in report["metrics"]
    without = [c for c in report["checks"] if c["id"] not in ("sharpe_confidence", "track_record")]
    from monte_neo.verify.schema import aggregate_verdict

    assert aggregate_verdict(without) == report["verdict"]  # they never change the verdict
