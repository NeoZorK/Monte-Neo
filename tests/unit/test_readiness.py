"""Alpha Readiness Level: levels stack, missing evidence is 'not assessed', a look-ahead failure blocks level 2."""

from __future__ import annotations

from monte_neo.alpha import validate_alpha
from monte_neo.alpha.report import demo_panel
from monte_neo.readiness import LEVELS, readiness


def _rep(**statuses: str) -> dict:
    return {"checks": [{"id": k, "category": "lookahead" if k.startswith("lookahead") else "statistics", "status": v}
                       for k, v in statuses.items()]}


FULL = dict(
    data_integrity="pass", lookahead_truncation="pass", net_profitability="pass", cost_margin="pass", ic="info", signal_placebo="pass",
    selection_adjusted_sharpe="pass", trial_ledger="pass", residual_alpha="pass", hidden_short_volatility="pass", deflated_sharpe="pass", market_impact="pass",
    synthetic_market_null="pass", universe_subsampling="pass", start_date_sensitivity="pass",
    rebalance_timing_luck="pass", marginal_sharpe="pass", live_vs_backtest="pass", alpha_death_monitor="info", live_source="pass",
)


def test_all_evidence_gives_nine() -> None:
    r = readiness(_rep(**FULL))
    assert r["level"] == 9 and r["summary"].startswith("ARL 9/9") and len(r["levels"]) == len(LEVELS) == 9


def test_first_gap_stops_the_level() -> None:
    ev = dict(FULL)
    ev["synthetic_market_null"] = "warn"  # rebalance_timing_luck has an alternative (cost_margin), this one has none here
    r = readiness(_rep(**ev))
    assert r["level"] == 6 and "blocked at 7" in r["summary"] and "synthetic_market_null" in r["summary"]
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


def test_level_four_needs_the_deflated_sharpe_floor() -> None:
    """arl-rules/2: the Deflated Sharpe of the certificate must reach 0.8, computed with at least the project's trials."""
    ev = {k: v for k, v in FULL.items() if k != "selection_adjusted_sharpe"}
    cert = _rep(**ev)
    assert readiness(cert)["levels"][3]["state"] == "not assessed"  # no metric: not assessed, never passed
    cert["metrics"], cert["reproducibility"] = {"deflated_sharpe": 0.95}, {"n_trials": 10}
    assert readiness(cert)["level"] == 9
    assert readiness(cert, n_trials=50)["level"] == 3  # the certificate counted fewer trials than the project tried
    low = readiness({**cert, "metrics": {"deflated_sharpe": 0.6}})
    assert low["level"] == 3 and low["levels"][3]["blocking"] == ["selection_adjusted_sharpe"]


def test_level_five_blockers_of_arl_rules_2() -> None:
    """A check that ran and warned blocks level 5; a check that did not run (not applicable) does not."""
    assert readiness(_rep(**FULL))["level"] == 9
    for check in ("universe_subsampling", "noise_injection", "short_feasibility", "residual_vs_book",
                  "cross_market_close_alignment", "post_discovery_decay", "claim_consistency", "universe_lookahead"):
        r = readiness(_rep(**{**FULL, check: "warn"}))
        assert r["level"] == 4 and check in r["levels"][4]["blocking"], check
    both = readiness(_rep(**{**FULL, "noise_injection": "fail", "post_discovery_decay": "warn"}))
    assert both["levels"][4]["blocking"] == ["noise_injection", "post_discovery_decay"]


def test_levels_above_three_need_evidence_of_the_trials() -> None:
    bare = {k: v for k, v in FULL.items() if k != "trial_ledger"}
    r = readiness(_rep(**bare))
    assert r["level"] == 3 and r["ceilings"][0]["check"] == "trial_evidence" and r["levels"][3]["state"] == "capped"
    assert readiness(_rep(**{**bare, "trial_ledger": "warn"}))["level"] == 9  # a ledger that corrected n_trials is still evidence
    assert readiness(_rep(**{**bare, "trial_ledger": "fail"}))["level"] == 3  # a changed ledger is not
    reg = _rep(**bare)
    reg["checks"].append({"id": "preregistration", "category": "statistics", "status": "info",
                          "details": {"found": True, "same_code": True, "before_first_verification": True}})
    assert readiness(reg)["level"] == 9
    late = _rep(**bare)
    late["checks"].append({"id": "preregistration", "category": "statistics", "status": "info",
                           "details": {"found": True, "same_code": True, "before_first_verification": False}})
    assert readiness(late)["level"] == 3
    hyg = _rep(**bare)
    hyg["checks"].append({"id": "research_hygiene", "category": "statistics", "status": "info",
                          "details": {"score": 2, "missing": ["registered", "holdout_used"], "ledger_variants": 40}})
    assert readiness(hyg)["level"] == 9


def test_level_three_needs_a_cost_margin_on_the_single_strategy_path() -> None:
    thin = readiness(_rep(**{**FULL, "cost_margin": "warn"}))
    assert thin["level"] == 2 and thin["levels"][2]["state"] == "failed" and "cost_margin" in thin["levels"][2]["blocking"]
    from monte_neo.verify.checks import COST_MARGIN_MIN
    assert COST_MARGIN_MIN == 3.0
