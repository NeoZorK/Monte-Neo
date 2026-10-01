"""Arrival-time traps and honest controls for ``verify_quotes``.

Traps must draw the named warning. Honest controls (slow strategies with a real edge, at different latencies
and seeds) must come back PASS with no warning: a check that accuses an honest strategy does not ship.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify.quotes import synthetic_feeds, synthetic_quotes
from monte_neo.verify.quotes_verdict import verify_quotes
from monte_neo.verify.verdict import model_from_costs

MODEL = model_from_costs(commission_bps=0.2, slippage_bps=0.15)


def react_to_last_bar(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["close"].diff().fillna(0.0).to_numpy())


def three_bar_trend(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["close"].diff(3).fillna(0.0).to_numpy())


def _statuses(report: dict) -> dict[str, str]:
    return {c["id"]: c["status"] for c in report["checks"]}


TRAPS = [
    ("exchange-clock momentum on 10 ms bars", 10.0, "arrival_lookahead"),
    ("fragile: one more p95 of delay erases the edge", 50.0, "latency_tolerance"),
    ("lucky latency: most redraws of the latency lose", 100.0, "latency_monte_carlo"),
]


@pytest.mark.parametrize(("name", "bar_ms", "check_id"), TRAPS, ids=[t[0] for t in TRAPS])
def test_trap_draws_its_warning(name: str, bar_ms: float, check_id: str) -> None:
    report = verify_quotes(synthetic_quotes(30_000, rho=0.5), signal_fn=react_to_last_bar, bar_ms=bar_ms, model=MODEL, samples=12)
    assert _statuses(report)[check_id] == "warn", name
    assert report["verdict"] == "PASS_WITH_WARNINGS"


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_honest_slow_strategy_is_not_accused(seed: int) -> None:
    quotes = synthetic_quotes(150_000, seed=seed, rho=0.0, drift=4e-6, regime_steps=3000)
    report = verify_quotes(quotes, signal_fn=three_bar_trend, bar_ms=1000.0, model=MODEL, samples=8)
    assert report["verdict"] == "PASS", _statuses(report)
    assert "warn" not in _statuses(report).values()


@pytest.mark.parametrize("median_latency_ms", [5.0, 20.0, 60.0])
def test_honest_strategy_passes_at_any_realistic_latency(median_latency_ms: float) -> None:
    quotes = synthetic_quotes(150_000, rho=0.0, drift=4e-6, regime_steps=3000, median_latency_ms=median_latency_ms)
    report = verify_quotes(quotes, signal_fn=three_bar_trend, bar_ms=2000.0, model=MODEL, samples=8)
    assert report["verdict"] == "PASS", _statuses(report)


def test_trap_the_edge_lives_in_instant_order_execution() -> None:
    """Profitable when the fill is instant, a loss once the order takes 50 ms to reach the market."""
    quotes = synthetic_quotes(30_000, rho=0.5)
    instant = verify_quotes(quotes, signal_fn=react_to_last_bar, bar_ms=50.0, model=MODEL, samples=4)
    delayed = verify_quotes(quotes, signal_fn=react_to_last_bar, bar_ms=50.0, model=MODEL, samples=4, order_latency_ms=50.0)
    assert _statuses(instant)["net_profitability"] == "pass" and instant["verdict"] != "REJECT"
    assert _statuses(delayed)["net_profitability"] == "fail" and delayed["verdict"] == "REJECT"
    assert "50 ms order delay" in next(c for c in delayed["checks"] if c["id"] == "net_profitability")["summary"]


def test_honest_strategy_survives_a_realistic_order_delay() -> None:
    quotes = synthetic_quotes(150_000, rho=0.0, drift=4e-6, regime_steps=3000)
    report = verify_quotes(quotes, signal_fn=three_bar_trend, bar_ms=1000.0, model=MODEL, samples=8, order_latency_ms=50.0)
    assert report["verdict"] == "PASS", _statuses(report)


def lead_lag(df: pd.DataFrame) -> np.ndarray:
    """Trade LAG on the move of LEAD."""
    return np.sign(df["LEAD_SIM_close"].diff(3).fillna(0.0).to_numpy())


def foresight(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["close"].shift(-1) - df["close"]).fillna(0.0).to_numpy()


LEAD_LAG = dict(signal_fn=lead_lag, symbol="LAG@SIM", feeds=["LEAD@SIM"], bar_ms=10.0, model=model_from_costs(commission_bps=0.1, slippage_bps=0.15), samples=4)


@pytest.mark.parametrize("leader_latency_ms", [30.0, 80.0, 150.0])
def test_trap_latency_arbitrage_the_leader_arrives_after_the_follower_moved(leader_latency_ms: float) -> None:
    """The follower repeats the leader 30 ms later; once the leader's data is that late, the edge is gone."""
    quotes = synthetic_feeds(20_000, leader_latency_ms=leader_latency_ms, follower_latency_ms=2.0)
    report = verify_quotes(quotes, probes=False, **LEAD_LAG)
    assert _statuses(report)["arrival_lookahead"] == "warn" and report["metrics"]["return_exchange_clock"] > 0 > report["metrics"]["return_arrival_clock"]


@pytest.mark.parametrize("leader_latency_ms", [1.0, 5.0])
def test_honest_latency_arbitrage_with_a_fast_leader_is_not_accused(leader_latency_ms: float) -> None:
    quotes = synthetic_feeds(20_000, leader_latency_ms=leader_latency_ms, follower_latency_ms=2.0)
    report = verify_quotes(quotes, probes=False, **LEAD_LAG)
    assert report["verdict"] == "PASS", _statuses(report)


def test_trap_foresight_is_a_leak_on_every_clock_and_the_probes_catch_it() -> None:
    quotes = synthetic_quotes(20_000, rho=0.0, drift=4e-6, regime_steps=3000)
    report = verify_quotes(quotes, signal_fn=foresight, bar_ms=1000.0, model=MODEL, samples=2)
    assert report["verdict"] == "REJECT" and _statuses(report)["lookahead_truncation"] == "fail"


@pytest.mark.parametrize("spec", ["lognormal:5,15", "lognormal:20,54", "constant:30"])
def test_honest_strategy_passes_under_an_assumed_latency(spec: str) -> None:
    table = synthetic_quotes(150_000, rho=0.0, drift=4e-6, regime_steps=3000).drop(columns=["latency_ms"])
    report = verify_quotes(table, signal_fn=three_bar_trend, bar_ms=1000.0, model=MODEL, samples=8, latency_model=spec)
    assert report["verdict"] == "PASS", _statuses(report)
