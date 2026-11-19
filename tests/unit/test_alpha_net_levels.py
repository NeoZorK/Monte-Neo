"""ARL levels 3 and 6 on the alpha path are read from the net returns of the executable portfolio, with the project's n_trials."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.alpha import demo_panel, validate_alpha
from monte_neo.alpha.executable import cost_sensitivity_row, executable_returns, net_deflated_sharpe_row
from monte_neo.alpha.families_run import portfolio_returns
from monte_neo.alpha.multiple_testing import hlz_hurdle
from monte_neo.alpha.panel import build_panel
from monte_neo.readiness import readiness

PRICES, REAL, _ = demo_panel(5, 40, 750)
PRICES = PRICES.assign(volume=np.random.default_rng(0).uniform(2e5, 6e5, len(PRICES)))
PANEL = build_panel(PRICES, REAL)


def _rep(aum, n_trials=1, **kw):
    rep = validate_alpha(PRICES, REAL, aum=aum, n_trials=n_trials, placebos=30, seed=0, **kw)
    return rep, {c["id"]: c for c in rep["checks"]}


def _level(rep, n):
    return next(lv for lv in rep["readiness"]["levels"] if lv["level"] == n)


def _alpha(*rows):
    return {"schema": "alpha-report/1", "metrics": {}, "reproducibility": {"settings": {}},
            "checks": [{"id": i, "status": s, "category": "statistics", "summary": "", "details": d or {}} for i, s, d in rows]}


# ---------------------------------------------------------------- the rules themselves
@pytest.mark.parametrize(("hlz", "met"), [("info", False), ("warn", False), ("pass", True)])
def test_level_6_needs_a_passing_hurdle_not_an_information_row(hlz, met) -> None:
    rep = readiness(alpha=_alpha(("hlz_hurdle", hlz, None), ("min_backtest_length", "pass", {"years_available": 5.0})))
    assert (next(lv for lv in rep["levels"] if lv["level"] == 6)["state"] == "met") is met


@pytest.mark.parametrize(("cost", "state"), [("pass", "met"), ("warn", "met"), ("fail", "failed"), (None, "not assessed")])
def test_level_3_on_the_alpha_path_needs_the_cost_sensitivity_too(cost, state) -> None:
    rows = [("market_impact", "pass", None)] + ([("cost_sensitivity", cost, None)] if cost else [])
    assert next(lv for lv in readiness(alpha=_alpha(*rows))["levels"] if lv["level"] == 3)["state"] == state
    assert next(lv for lv in readiness(alpha=_alpha(("market_impact", "fail", None), ("cost_sensitivity", "pass", None)))["levels"] if lv["level"] == 3)["state"] == "failed"


# ---------------------------------------------------------------- trap: a significant signal that costs eat
def test_signal_eaten_by_costs_gets_neither_level_3_nor_6() -> None:
    rep, ids = _rep(5e6, n_trials=114)
    gross = hlz_hurdle(portfolio_returns(PANEL, 5)[0])
    assert ids["ic"]["status"] in ("info", "pass") and gross["status"] == "pass"  # as a signal it looks significant, and on gross returns it would have passed
    assert ids["market_impact"]["status"] == "fail" and ids["cost_sensitivity"]["status"] == "fail"
    assert ids["hlz_hurdle"]["status"] == "info" and ids["deflated_sharpe"]["status"] == "fail" and ids["deflated_sharpe"]["details"]["returns"] == "net of costs"
    assert rep["readiness"]["level"] < 3 and _level(rep, 3)["state"] == "failed" and _level(rep, 6)["state"] != "met"


# ---------------------------------------------------------------- an honest strong portfolio still gets them
def test_honest_strong_portfolio_reaches_level_6() -> None:
    rep, ids = _rep(1e4)
    assert ids["cost_sensitivity"]["status"] == "pass" and ids["deflated_sharpe"]["status"] == "pass" and ids["hlz_hurdle"]["status"] == "pass"
    assert rep["readiness"]["level"] >= 6


def test_more_trials_lower_the_deflated_sharpe_and_costs_are_named() -> None:
    _, one = _rep(1e5, n_trials=1)
    _, many = _rep(1e5, n_trials=114)
    assert many["deflated_sharpe"]["details"]["deflated_sharpe"] < one["deflated_sharpe"]["details"]["deflated_sharpe"]
    assert many["deflated_sharpe"]["details"]["n_trials"] == 114 and "square-root impact at AUM" in many["deflated_sharpe"]["details"]["costs"]


def test_family_f_uses_net_not_gross_returns() -> None:
    _, ids = _rep(1e5)
    net_t = ids["hlz_hurdle"]["details"]["t_stat"]
    gross_t = hlz_hurdle(portfolio_returns(PANEL, 5)[0])["details"]["t_stat"]
    assert net_t < gross_t


def test_without_an_aum_only_commission_is_charged_and_the_rows_say_so() -> None:
    _, ids = _rep(None)
    assert "commission 1 bp only" in ids["cost_sensitivity"]["summary"] and "market impact is not included" in ids["deflated_sharpe"]["details"]["costs"]
    assert "market_impact" in ids and ids["market_impact"]["status"] == "skip"


def test_funding_enters_the_net_returns() -> None:
    funding = PRICES[["timestamp", "symbol"]].assign(funding_bps=2.0)
    _, plain = _rep(1e4)
    _, paid = _rep(1e4, funding=funding)
    assert "real funding" in paid["deflated_sharpe"]["details"]["costs"] and "real funding" not in plain["deflated_sharpe"]["details"]["costs"]


# ---------------------------------------------------------------- the helpers
def test_executable_returns_and_row_boundaries() -> None:
    w = np.zeros((60, 3))
    w[:, 0], w[:, 1] = 0.5, -0.5
    close = 100 * np.cumprod(np.full((60, 3), 1.001), axis=0)
    vol = np.full((60, 3), 1e6)
    gross, _ = executable_returns(w, close, None, None, cost_multiple=0.0)
    net, info = executable_returns(w, close, vol, 1e6)
    assert net.sum() < gross.sum() and "impact at AUM" in info["costs"]
    two, _ = executable_returns(w, close, vol, 1e6, cost_multiple=2.0)
    assert two.sum() < net.sum()
    f = np.full((60, 3), 5.0)
    assert executable_returns(w, close, vol, 1e6, funding_bps=f)[0].shape == net.shape
    stamps = pd.bdate_range("2020-01-01", periods=60)
    del stamps
    assert cost_sensitivity_row(w, close, vol, 1e6, 252.0)["status"] in ("pass", "warn", "fail")
    assert net_deflated_sharpe_row(np.zeros(100) + 1e-4 * np.arange(100) % 3, 1, 252.0, "x")["status"] in ("pass", "warn", "fail")
