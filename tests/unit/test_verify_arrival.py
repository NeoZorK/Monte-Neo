"""arrival: look-ahead on the arrival clock, latency scan and latency Monte Carlo."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.arrival import (
    arrival_lookahead,
    arrival_row,
    latency_monte_carlo,
    latency_row,
    latency_scan,
    monte_carlo_row,
)
from monte_neo.verify.checks import NEXT_ACTIONS
from monte_neo.verify.quotes import Quotes, load_quotes, synthetic_quotes
from monte_neo.verify.schema import CATEGORIES

MODEL = ExecutionModel(commission_bps=0.2, slippage_bps=0.0, warmup_bars=5)


def trend(df: pd.DataFrame) -> np.ndarray:
    """Slow honest rule: sign of the last three bars' move."""
    return np.sign(df["close"].diff(3).fillna(0.0).to_numpy())


def momentum(df: pd.DataFrame) -> np.ndarray:
    """Reacts to the last bar: profitable only if the bar is known the moment it closes."""
    return np.sign(df["close"].diff().fillna(0.0).to_numpy())


@pytest.fixture(scope="module")
def slow_quotes() -> Quotes:
    return load_quotes(synthetic_quotes(40_000, rho=0.0, drift=1.5e-5, regime_steps=3000))


@pytest.fixture(scope="module")
def fast_quotes() -> Quotes:
    return load_quotes(synthetic_quotes(30_000, rho=0.5))


def test_honest_slow_strategy_keeps_its_profit_on_the_arrival_clock(slow_quotes: Quotes) -> None:
    info = arrival_lookahead(slow_quotes, trend, MODEL, bar_ms=1000.0)
    assert info["status"] == "pass"
    assert info["return_exchange_clock"] > 0 and info["return_arrival_clock"] > 0
    assert info["retained"] == pytest.approx(1.0, abs=0.15)
    row = arrival_row(info)
    assert row["id"] == "arrival_lookahead" and row["status"] == "pass" and "keeps" in row["summary"]


def test_fast_strategy_that_needs_data_before_it_arrived_is_flagged(fast_quotes: Quotes) -> None:
    info = arrival_lookahead(fast_quotes, momentum, MODEL, bar_ms=10.0)
    assert info["status"] == "warn"
    assert info["return_exchange_clock"] > 0 >= info["return_arrival_clock"]
    row = arrival_row(info)
    assert row["status"] == "warn" and "exchange time" in row["summary"] and "arrival time" in row["summary"]


def test_arrival_check_skips_without_latency_or_without_profit(fast_quotes: Quotes) -> None:
    no_latency = load_quotes(synthetic_quotes(5_000, rho=0.5).assign(latency_ms=0.0))
    info = arrival_lookahead(no_latency, momentum, MODEL, bar_ms=10.0)
    assert info["status"] == "skip"
    assert "no latency" in arrival_row(info)["summary"]

    def short(df: pd.DataFrame) -> np.ndarray:
        return -momentum(df)

    losing = arrival_lookahead(fast_quotes, short, MODEL, bar_ms=10.0)
    assert losing["status"] == "skip" and losing["retained"] is None
    assert "not profitable" in arrival_row(losing)["summary"]


def test_scan_of_an_honest_strategy_survives_every_delay(slow_quotes: Quotes) -> None:
    info = latency_scan(slow_quotes, trend, MODEL, bar_ms=1000.0)
    assert info["status"] == "pass" and info["profit_vanishes_at_extra_ms"] is None
    assert "0" in info["return_by_extra_ms"]
    assert f"{info['p95_latency_ms']:g}" in info["return_by_extra_ms"]
    assert "survives" in latency_row(info)["summary"]


def test_scan_finds_where_the_profit_of_a_fast_strategy_vanishes(fast_quotes: Quotes) -> None:
    info = latency_scan(fast_quotes, momentum, MODEL, bar_ms=50.0)
    assert info["status"] == "warn"
    assert 0.0 < info["profit_vanishes_at_extra_ms"] <= info["p95_latency_ms"]
    row = latency_row(info)
    assert row["category"] in CATEGORIES and "vanishes" in row["summary"]


def test_scan_without_a_zero_point_still_measures_the_observed_clock(fast_quotes: Quotes) -> None:
    info = latency_scan(fast_quotes, momentum, MODEL, bar_ms=50.0, extra_ms=(20.0, 100.0))
    assert "0" not in info["return_by_extra_ms"]
    assert info["status"] == "warn"  # the baseline is still measured, only not reported as a scan point


def test_scan_skips_a_strategy_that_does_not_earn_on_the_arrival_clock(fast_quotes: Quotes) -> None:
    info = latency_scan(fast_quotes, momentum, MODEL, bar_ms=10.0)
    assert info["status"] == "skip" and info["profit_vanishes_at_extra_ms"] is None
    assert "not profitable" in latency_row(info)["summary"]


def test_monte_carlo_is_reproducible_for_a_seed(slow_quotes: Quotes) -> None:
    a = latency_monte_carlo(slow_quotes, trend, MODEL, bar_ms=1000.0, samples=8, seed=5)
    b = latency_monte_carlo(slow_quotes, trend, MODEL, bar_ms=1000.0, samples=8, seed=5)
    c = latency_monte_carlo(slow_quotes, trend, MODEL, bar_ms=1000.0, samples=8, seed=6)
    assert a == b and a != c
    assert a["status"] == "pass" and a["probability_of_loss"] == 0.0
    assert a["return_p5"] <= a["return_p50"] <= a["return_p95"]
    assert "0% of 8" in monte_carlo_row(a)["summary"]


def test_monte_carlo_warns_when_the_observed_profit_was_lucky_latency(fast_quotes: Quotes) -> None:
    info = latency_monte_carlo(fast_quotes, momentum, MODEL, bar_ms=100.0, samples=12)
    assert info["observed_return"] > 0 and info["probability_of_loss"] > 0.5 and info["status"] == "warn"
    assert monte_carlo_row(info)["status"] == "warn"


def test_monte_carlo_draws_inside_each_venue() -> None:
    df = synthetic_quotes(6_000, rho=0.5)
    df["venue"] = np.where(np.arange(len(df)) % 2 == 0, "FAST", "SLOW")
    df.loc[df["venue"] == "FAST", "latency_ms"] = 5.0
    df.loc[df["venue"] == "SLOW", "latency_ms"] = 200.0
    q = load_quotes(df)
    info = latency_monte_carlo(q, momentum, MODEL, bar_ms=100.0, samples=3)
    assert info["samples"] == 3 and info["status"] in ("pass", "warn", "skip")


def test_monte_carlo_skips_when_not_profitable(fast_quotes: Quotes) -> None:
    info = latency_monte_carlo(fast_quotes, momentum, MODEL, bar_ms=10.0, samples=2)
    assert info["status"] == "skip"
    assert "not profitable" in monte_carlo_row(info)["summary"]


def test_next_actions_exist_for_the_new_ids() -> None:
    for check_id in ("quote_quality", "arrival_lookahead", "latency_tolerance", "latency_monte_carlo"):
        assert check_id in NEXT_ACTIONS


def test_order_latency_lowers_the_return_of_a_fast_strategy(fast_quotes: Quotes) -> None:
    plain = arrival_lookahead(fast_quotes, momentum, MODEL, bar_ms=50.0)
    slow_fill = arrival_lookahead(fast_quotes, momentum, MODEL, bar_ms=50.0, order_latency_ms=100.0)
    assert plain["order_latency_ms"] == 0.0 and slow_fill["order_latency_ms"] == 100.0
    assert slow_fill["return_exchange_clock"] < plain["return_exchange_clock"]


def test_order_latency_reaches_the_scan_and_the_monte_carlo(fast_quotes: Quotes) -> None:
    scan0 = latency_scan(fast_quotes, momentum, MODEL, bar_ms=50.0)
    scan1 = latency_scan(fast_quotes, momentum, MODEL, bar_ms=50.0, order_latency_ms=100.0)
    assert scan0["return_by_extra_ms"] != scan1["return_by_extra_ms"]
    mc0 = latency_monte_carlo(fast_quotes, momentum, MODEL, bar_ms=100.0, samples=4)
    mc1 = latency_monte_carlo(fast_quotes, momentum, MODEL, bar_ms=100.0, samples=4, order_latency_ms=200.0)
    assert mc0["observed_return"] != mc1["observed_return"]
