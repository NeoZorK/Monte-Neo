"""Arrival-time traps and honest controls for ``verify_quotes``.

Traps must draw the named warning. Honest controls (slow strategies with a real edge, at different latencies
and seeds) must come back PASS with no warning: a check that accuses an honest strategy does not ship.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify.quotes import synthetic_quotes
from monte_neo.verify.quotes_verdict import verify_quotes
from monte_neo.verify.verdict import model_from_costs

MODEL = model_from_costs(commission_bps=0.2, slippage_bps=0.0)


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
    quotes = synthetic_quotes(40_000, seed=seed, rho=0.0, drift=1.5e-5, regime_steps=3000)
    report = verify_quotes(quotes, signal_fn=three_bar_trend, bar_ms=1000.0, model=MODEL, samples=8)
    assert report["verdict"] == "PASS", _statuses(report)
    assert "warn" not in _statuses(report).values()


@pytest.mark.parametrize("median_latency_ms", [5.0, 20.0, 60.0])
def test_honest_strategy_passes_at_any_realistic_latency(median_latency_ms: float) -> None:
    quotes = synthetic_quotes(40_000, rho=0.0, drift=1.5e-5, regime_steps=3000, median_latency_ms=median_latency_ms)
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
    quotes = synthetic_quotes(40_000, rho=0.0, drift=1.5e-5, regime_steps=3000)
    report = verify_quotes(quotes, signal_fn=three_bar_trend, bar_ms=1000.0, model=MODEL, samples=8, order_latency_ms=50.0)
    assert report["verdict"] == "PASS", _statuses(report)
