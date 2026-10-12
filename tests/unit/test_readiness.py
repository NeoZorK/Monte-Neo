"""Alpha Readiness Level: levels stack, missing evidence is 'not assessed', a look-ahead failure blocks level 2."""

from __future__ import annotations

from monte_neo.alpha import validate_alpha
from monte_neo.alpha.report import demo_panel
from monte_neo.readiness import LEVELS, readiness


def _rep(**statuses: str) -> dict:
    return {"checks": [{"id": k, "category": "lookahead" if k.startswith("lookahead") else "statistics", "status": v}
                       for k, v in statuses.items()]}


FULL = dict(
    data_integrity="pass", lookahead_truncation="pass", net_profitability="pass", ic="info", signal_placebo="pass",
    residual_alpha="pass", hidden_short_volatility="pass", deflated_sharpe="pass", market_impact="pass",
    synthetic_market_null="pass", universe_subsampling="pass", start_date_sensitivity="pass",
    rebalance_timing_luck="pass", marginal_sharpe="pass", live_vs_backtest="pass", alpha_death_monitor="info",
)


def test_all_evidence_gives_nine() -> None:
    r = readiness(_rep(**FULL))
    assert r["level"] == 9 and r["summary"].startswith("ARL 9/9") and len(r["levels"]) == len(LEVELS) == 9


def test_first_gap_stops_the_level() -> None:
    ev = dict(FULL)
    ev["rebalance_timing_luck"] = "warn"
    r = readiness(_rep(**ev))
    assert r["level"] == 6 and "blocked at 7" in r["summary"] and "rebalance_timing_luck" in r["summary"]
    assert r["levels"][6]["state"] == "failed" and r["levels"][7]["state"] == "met"  # higher levels are shown, not counted


def test_missing_evidence_is_not_assessed() -> None:
    ev = {k: v for k, v in FULL.items() if k != "marginal_sharpe"}
    r = readiness(_rep(**ev))
    assert r["level"] == 7 and r["levels"][7]["state"] == "not assessed"
    assert "not assessed beyond 7" in r["summary"] and r["next_step"].endswith("--book book.csv")


def test_any_lookahead_failure_blocks_level_two() -> None:
    r = readiness(_rep(**{**FULL, "lookahead_perturbation": "fail"}))
    assert r["level"] == 1 and r["levels"][1]["blocking"] == ["lookahead_perturbation"]


def test_skipped_checks_do_not_count() -> None:
    r = readiness(_rep(**{**FULL, "lookahead_truncation": "skip", "universe_lookahead": "skip"}))
    assert r["level"] == 1 and r["levels"][1]["state"] == "not assessed"


def test_alpha_report_carries_its_level() -> None:
    prices, real, noise = demo_panel(2)
    good = validate_alpha(prices, real, placebos=60, aum=2e5)
    bad = validate_alpha(prices, noise, placebos=60, aum=2e5)
    assert good["readiness"]["level"] > bad["readiness"]["level"] >= 1
    assert "not the investment" in good["readiness"]["disclaimer"]
