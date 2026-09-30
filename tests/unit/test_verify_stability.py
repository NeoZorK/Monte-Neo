"""Rolling-window stability row (context only)."""

from __future__ import annotations

import numpy as np

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import verify_strategy
from monte_neo.verify.stability import rolling_stability, stability_row


def test_windows_cover_every_bar_and_count_the_winners() -> None:
    rets = np.concatenate([np.full(100, 0.001), np.full(100, -0.001)] * 3)
    info = rolling_stability(rets, 252.0)
    assert info["windows"] == 6 and info["bars_per_window"] == 100
    assert info["positive"] == 3
    assert info["worst_return"] < 0 < info["best_return"]
    assert len(info["returns"]) == len(info["sharpe_annualized"]) == 6


def test_too_short_a_sample_gives_nothing() -> None:
    assert rolling_stability(np.zeros(100), 252.0) == {}
    assert stability_row({})["status"] == "skip"


def test_non_finite_returns_are_dropped() -> None:
    rets = np.random.default_rng(0).standard_normal(400) * 0.01
    rets[10] = np.nan
    assert rolling_stability(rets, 252.0)["windows"] == 6


def test_row_is_context_only_and_appears_in_a_certificate() -> None:
    df = synthetic_ohlcv(1200, seed=4)
    report = verify_strategy(df, signals=np.sign(np.sin(np.arange(len(df)) / 15.0)))
    row = next(c for c in report["checks"] if c["id"] == "walk_forward_stability")
    assert row["status"] == "info" and "equal windows" in row["summary"]
    assert report["metrics"]["windows_positive"] == row["details"]["positive"]
