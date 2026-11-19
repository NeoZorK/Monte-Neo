"""ARL depth: no evidence scores 0, the hard invariants, and that depth never lifts a level."""

from __future__ import annotations

import copy

import pytest

from monte_neo import readiness as rd
from monte_neo.arl_depth import MET, NA, UNMET, Evidence, depth_for_level
from monte_neo.arl_rules import load_rules
from monte_neo.readiness import readiness


def _row(cid: str, status: str = "pass", category: str = "statistics", **details: object) -> dict:
    return {"id": cid, "status": status, "category": category, "summary": "s", "details": details}


def _cert(*rows: dict, n_trials: int = 1) -> dict:
    return {"checks": list(rows), "metrics": {}, "reproducibility": {"n_trials": n_trials}}


def _ev(*rows: dict, n_trials: int = 1, holdout: dict | None = None, metrics: dict | None = None, extra: dict | None = None) -> Evidence:
    return Evidence({r["id"]: r for r in rows}, metrics=metrics or {}, holdout=holdout, n_trials=n_trials, extra=extra)


def _state(level: int, cid: str, ev: Evidence) -> str:
    return next(c["state"] for c in depth_for_level(level, ev)["criteria"] if c["id"] == cid)


VALID = {"valid": True, "opens": 1, "reason": None, "checks": []}


def _hold(*rows: dict) -> dict:
    return {**VALID, "checks": list(rows)}


def test_no_evidence_means_depth_zero_and_not_assessed_with_a_command() -> None:
    rep = readiness(None)
    assert rep["level"] == 0 and rep["depth"] == 0 and rep["headline"].startswith("ARL 0, depth 0/4 (arl-rules/1, provisional)")
    ev = _ev()
    for n in range(1, 10):
        d = depth_for_level(n, ev)
        assert d["depth"] == 0
        assert all(c["state"] == NA and c["needs"] for c in d["criteria"]), n


def test_boundaries_of_numeric_criteria() -> None:
    assert _state(3, "D3", _ev(_row("sample_size", n_closed_trades=99))) == UNMET
    assert _state(3, "D3", _ev(_row("sample_size", n_closed_trades=100))) == MET
    assert _state(6, "D1", _ev(_row("deflated_sharpe", deflated_sharpe=0.989, n_trials=1))) == UNMET
    assert _state(6, "D1", _ev(_row("deflated_sharpe", deflated_sharpe=0.99, n_trials=1))) == MET
    assert _state(6, "D2", _ev(_row("pbo", pbo=0.2))) == UNMET and _state(6, "D2", _ev(_row("pbo", pbo=0.199))) == MET
    for years, want in ((2.99, UNMET), (3.0, MET)):
        ev = _ev(_row("deflated_sharpe", n_obs=years * 252, periods_per_year=252, deflated_sharpe=0.5, n_trials=1))
        assert _state(1, "D3", ev) == want


def test_ratio_and_status_rules() -> None:
    cost = lambda be: _ev(_row("cost_margin", breakeven_bps=be), _row("costs_modeled", per_side_cost_bps=10.0))  # noqa: E731
    assert _state(3, "D1", cost(49.9)) == UNMET and _state(3, "D1", cost(50.0)) == MET
    assert _state(3, "D1", _ev(_row("cost_margin", breakeven_bps=50.0))) == NA  # modelled cost unknown
    wf = lambda pos: _ev(_row("walk_forward_stability", positive=pos, windows=6))  # noqa: E731
    assert _state(3, "D2", wf(4)) == UNMET and _state(3, "D2", wf(5)) == MET
    assert _state(7, "D1", _ev(_row("cost_sensitivity"), _row("delay_sensitivity"))) == MET
    assert _state(7, "D1", _ev(_row("cost_sensitivity"), _row("delay_sensitivity", "warn"))) == UNMET
    assert _state(7, "D1", _ev(_row("cost_sensitivity"))) == NA


def test_optional_parts_are_ignored_only_when_absent() -> None:
    base = _row("residual_alpha")
    assert _state(5, "D2", _ev(base)) == MET
    assert _state(5, "D2", _ev(base, _row("alpha_after_beta"))) == MET
    assert _state(5, "D2", _ev(base, _row("alpha_after_beta", "warn"))) == UNMET


def test_trials_are_paid_at_levels_four_to_six() -> None:
    p = lambda v, n: _ev(_row("signal_placebo", p_value=v), n_trials=n)  # noqa: E731
    assert _state(4, "D1", p(0.009, 1)) == MET
    assert _state(4, "D1", p(0.004, 2)) == MET and _state(4, "D1", p(0.005, 2)) == UNMET  # 0.01 is the limit after multiplying by 2
    assert _state(4, "D1", p(0.00005, 199)) == MET and _state(4, "D1", p(0.00005, 200)) == UNMET
    t = lambda v, n: _ev(_row("residual_alpha", alpha_t=v), n_trials=n)  # noqa: E731
    assert _state(5, "D1", t(3.0, 1)) == MET and _state(5, "D1", t(2.99, 1)) == UNMET
    assert _state(5, "D1", t(3.0, 2)) == UNMET and _state(5, "D1", t(4.0, 2)) == MET and _state(5, "D1", t(-4.0, 1)) == UNMET
    assert _state(6, "D1", _ev(_row("deflated_sharpe", deflated_sharpe=0.999, n_trials=5), n_trials=40)) == UNMET  # computed with fewer trials
    assert _state(6, "D1", _ev(_row("deflated_sharpe", deflated_sharpe=0.999, n_trials=40), n_trials=40)) == MET


def test_project_trial_count_comes_from_every_source() -> None:
    cert = _cert(_row("signal_placebo", p_value=0.004), n_trials=1)
    assert readiness(cert)["n_trials_used"] == 1
    assert readiness(cert, n_trials=10)["n_trials_used"] == 10
    assert readiness(_cert(n_trials=7))["n_trials_used"] == 7
    assert readiness(None, alpha={"checks": [], "reproducibility": {"settings": {"n_trials": 9}}})["n_trials_used"] == 9
    assert readiness(_cert(_row("trial_ledger", counted=12, declared=12)))["n_trials_used"] == 12
    crit = lambda rep: next(c for c in rep["levels"][3]["depth_criteria"] if c["id"] == "D1")["state"]  # noqa: E731
    assert crit(readiness(cert)) == MET and crit(readiness(cert, n_trials=100)) == UNMET


def test_ledger_audit_criterion() -> None:
    assert _state(6, "D3", _ev(_row("trial_ledger", counted=5, declared=5))) == MET
    assert _state(6, "D3", _ev(_row("trial_ledger", counted=5, declared=3))) == UNMET
    assert _state(6, "D3", _ev(_row("trial_ledger", counted=5, declared=None))) == UNMET
    assert _state(6, "D3", _ev(_row("trial_ledger", "warn", counted=5, declared=3))) == UNMET  # status not pass
    assert _state(6, "D3", _ev()) == NA


def test_sealed_holdout_is_the_only_source_of_d4() -> None:
    assert _state(3, "D4", _ev(_row("net_profitability"))) == NA  # an in-sample pass is not out of sample
    assert _state(3, "D4", _ev(holdout=_hold(_row("net_profitability")))) == MET
    assert _state(3, "D4", _ev(holdout=_hold(_row("net_profitability", "fail")))) == UNMET
    assert _state(3, "D4", _ev(holdout=_hold())) == NA
    assert _state(6, "D4", _ev(holdout=_hold(_row("deflated_sharpe", deflated_sharpe=0.95)))) == MET
    assert _state(6, "D4", _ev(holdout=_hold(_row("deflated_sharpe", deflated_sharpe=0.94)))) == UNMET
    assert _state(2, "D4", _ev(holdout=_hold(_row("lookahead_truncation"), _row("lookahead_perturbation")))) == MET
    assert _state(8, "D4", _ev(holdout=_hold(_row("marginal_sharpe")))) == MET
    assert _state(7, "D4", _ev(holdout=_hold(_row("net_profitability"), _row("cost_realism")))) == MET


def test_reopened_holdout_zeroes_d4_everywhere() -> None:
    spoiled = {"valid": False, "opens": 1, "reason": "the sealed holdout was opened more than once", "checks": [_row("net_profitability")]}
    ev = _ev(_row("net_profitability"), holdout=spoiled, metrics={"live": {"source": "real_fills", "custody": "stmt"}})
    for n in range(1, 10):
        d4 = next(c for c in depth_for_level(n, ev)["criteria"] if c["id"] == "D4")
        assert d4["state"] == UNMET and "permanently" in d4["why"] and "more than once" in d4["why"], n


def test_lookahead_failure_caps_the_level_at_one() -> None:
    rows = [_row("data_integrity", category="integrity"), _row("lookahead_truncation", category="lookahead"), _row("net_profitability", category="economics")]
    assert readiness(_cert(*rows))["level"] == 3
    bad = [*rows[:1], _row("lookahead_perturbation", "fail", category="lookahead"), *rows[1:]]
    r = readiness(_cert(*bad))
    assert r["level"] == 1 and r["levels"][1]["state"] == "failed" and r["levels"][1]["blocking"] == ["lookahead_perturbation"]
    assert all(lv["depth"] == 0 for lv in r["levels"][1:])


def _live(source: str | None, custody: str | None = None, **more: object) -> dict:
    rows = [_row("live_vs_backtest"), _row("alpha_death_monitor", "info"), _row("live_source", "pass" if source == "real_fills" else "warn")]
    return {"checks": rows, "metrics": {"source": source, "custody": custody, "live_span_days": 200, "n_fills": 120, "live_sharpe_annualized": 1.0, **more}}


def _eight() -> dict:
    ids = ["data_integrity", "lookahead_truncation", "net_profitability", "timing_significance", "residual_alpha", "hidden_short_volatility",
           "deflated_sharpe", "market_impact", "synthetic_market_null", "universe_subsampling", "start_date_sensitivity",
           "rebalance_timing_luck", "marginal_sharpe"]
    return _cert(*[_row(i, category="lookahead" if i.startswith("look") else "statistics") for i in ids])


def test_paper_testnet_simulated_cap_at_eight_and_real_fills_need_custody_for_d4() -> None:
    for src in ("paper", "testnet", "simulated", None):
        r = readiness(_eight(), live=_live(src))
        assert r["level"] == 8, src
        assert {"check": "live_source", "max_level": 8, "why": "paper, testnet and simulated fills are not live"} in r["ceilings"]
    spoofed = _live("paper")
    spoofed["checks"][2] = _row("live_source", "pass")  # even a forged passing row cannot lift a paper source
    assert readiness(_eight(), live=spoofed)["level"] == 8
    real = readiness(_eight(), live=_live("real_fills", None))
    assert real["level"] == 9 and real["headline"].startswith("ARL 9")
    d4 = next(c for c in real["levels"][8]["depth_criteria"] if c["id"] == "D4")
    assert d4["state"] == UNMET
    full = readiness(_eight(), live=_live("real_fills", "broker statement 2026-11"))
    assert next(c for c in full["levels"][8]["depth_criteria"] if c["id"] == "D4")["state"] == MET
    assert full["levels"][8]["depth"] >= 2


def test_live_criteria_boundaries() -> None:
    cert = {"sharpe_ci95": [0.5, 1.5]}
    mk = lambda **m: _ev(metrics={"cert": cert, "live": {"live_sharpe_annualized": 1.0, "live_span_days": 182, "n_fills": 100, **m}})  # noqa: E731
    assert _state(9, "D1", mk()) == MET and _state(9, "D1", mk(live_sharpe_annualized=1.6)) == UNMET
    assert _state(9, "D1", _ev()) == NA
    assert _state(9, "D3", mk()) == MET and _state(9, "D3", mk(live_span_days=181)) == UNMET and _state(9, "D3", mk(n_fills=99)) == UNMET
    assert _state(9, "D2", _ev(extra={"live_regimes": True})) == MET and _state(9, "D2", _ev()) == NA


def test_depth_never_lifts_the_level() -> None:
    base = _eight()
    plain = readiness(base)
    rich = readiness(base, holdout=_hold(_row("net_profitability")), evidence={"fresh_fetch_hash": True, "book_stress": True, "live_regimes": True}, n_trials=1)
    assert plain["level"] == rich["level"]
    capped = readiness(_cert(_row("data_integrity", category="integrity"), _row("lookahead_truncation", category="lookahead"),
                             _row("net_profitability", category="economics"), _row("deflated_sharpe", deflated_sharpe=0.999, n_trials=1)))
    assert capped["level"] == 3 and capped["levels"][5]["depth"] == 0  # level 6 is not reached: depth 0 whatever the criteria say
    assert capped["levels"][5]["depth_if_reached"] >= 1 and not capped["levels"][5]["counts"]
    for rep in (plain, rich, capped):
        for lv in rep["levels"]:
            assert lv["depth"] == 0 or lv["counts"]
            assert 0 <= lv["depth"] <= 4
        assert rep["depth"] == next((lv["depth"] for lv in rep["levels"] if lv["level"] == rep["level"]), 0)


def test_next_actions_name_the_command_for_each_open_criterion() -> None:
    rep = readiness(_cert(_row("data_integrity", category="integrity")))
    assert rep["level"] == 1
    acts = rep["next_actions"]
    assert acts and all(a["command"] and a["state"] != MET for a in acts)
    assert {a["level"] for a in acts} <= {1, 2}
    assert any("monte-neo" in a["command"] or "freeze" in a["command"] for a in acts)


def test_rules_version_is_recorded_and_unknown_one_refused() -> None:
    rep = readiness(_cert(), rules_version="arl-rules/1")
    assert rep["rules_version"] == "arl-rules/1" and rep["provisional"] is True and "provisional" in rep["headline"]
    with pytest.raises(ValueError, match="unknown ARL rules version"):
        readiness(_cert(), rules_version="arl-rules/7")


def test_frozen_rules_drop_the_provisional_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    frozen = copy.deepcopy(load_rules())
    frozen["status"] = "frozen"
    monkeypatch.setattr(rd, "load_rules", lambda version=None: frozen)
    rep = rd.readiness(_cert())
    assert rep["provisional"] is False and rep["headline"].endswith("(arl-rules/1)")


def test_derived_values_missing_and_present() -> None:
    e = _ev(metrics={"alpha": {"n_dates": 1260, "n_symbols": 10}, "live": {}})
    assert e.derived("years") == pytest.approx(5.0) and e.derived("observations") == 12600
    assert e.derived("live_span_days") is None and e.derived("live_fills") is None and e.derived("custody") is None or e.derived("custody") == 0.0
    assert _ev().derived("years") is None and _ev().derived("observations") is None and _ev().derived("nope") is None
    mbl = _ev(_row("min_backtest_length", years_available=7.5))
    assert mbl.derived("years") == 7.5
    assert _ev(metrics={"live": {"custody": "x"}}).derived("custody") == 1.0
