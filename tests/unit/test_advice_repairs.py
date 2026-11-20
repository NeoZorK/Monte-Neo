"""Fix-it advice and repair candidates for the new checks."""

from __future__ import annotations

import json
from pathlib import Path

from monte_neo.mcp.tools import suggest_fix
from monte_neo.repair import plan
from monte_neo.repair.runtime import TRANSFORMS
from monte_neo.verify import checks as rows
from monte_neo.verify.fixes import advise


def _row(cid: str, status: str = "warn", **details: object) -> dict:
    return {"id": cid, "category": "statistics", "status": status, "summary": "s", "details": details}


def test_every_new_warning_has_an_action() -> None:
    for cid in ("rebalance_timing_luck", "selection_vs_timing_basket", "alpha_after_reference", "alpha_after_beta", "regime_stability",
                "cost_sensitivity", "cost_realism", "execution_capacity", "funding_borrow_stress", "publication_dates",
                "universe_membership", "survivorship"):
        assert rows.next_actions([_row(cid)]), cid
    assert "capped at 4" in rows.next_actions([_row("survivorship")])[0]


def test_rebalance_luck_gets_tranches_at_the_found_cadence() -> None:
    cands = plan.candidates([_row("rebalance_timing_luck", k=7)])
    assert cands and cands[0]["id"] == "R7" and cands[0]["steps"] == [("tranche", {"every": 7, "sleeves": 4})]
    assert not plan.candidates([_row("rebalance_timing_luck", "pass", k=7)])
    assert not plan.candidates([_row("rebalance_timing_luck", k=1)])  # no usable cadence
    assert not plan.candidates([_row("rebalance_timing_luck")])  # k unknown


def test_catalogue_maps_new_defects_to_declared_transforms() -> None:
    for cid in ("alpha_after_beta", "alpha_after_reference", "selection_vs_timing_basket", "cost_sensitivity", "cost_realism",
                "execution_capacity", "funding_borrow_stress"):
        rid, _, options = plan.ECONOMIC_REPAIRS[cid]
        assert rid.startswith("R") and options
        assert all(name in TRANSFORMS for steps in options for name, _ in steps), cid
    assert "delisted" in plan.NOT_REPAIRABLE["survivorship"] and "regime_stability" in plan.NOT_REPAIRABLE


def test_advise_lists_repairs_and_what_only_the_owner_can_do() -> None:
    report = {"checks": [
        _row("rebalance_timing_luck", k=5), _row("selection_vs_timing_basket"), _row("cost_realism", "fail"),
        _row("survivorship", integrity := "warn"), _row("regime_stability"), _row("net_profitability", "pass"),
        _row("return_smoothing"),  # no action, no repair: left out
    ]}
    adv = {a["check"]: a for a in advise(report)}
    assert set(adv) == {"rebalance_timing_luck", "selection_vs_timing_basket", "cost_realism", "survivorship", "regime_stability"}
    assert adv["rebalance_timing_luck"]["repair"][0]["steps"] == [["tranche", {"every": 5, "sleeves": 4}]]
    assert adv["selection_vs_timing_basket"]["repair"][0]["steps"] == [["neutral", {}]]
    assert {c["steps"][0][0] for c in adv["cost_realism"]["repair"]} == {"hold"}  # trade less often
    assert adv["survivorship"]["repair"] == [] and "delisted" in adv["survivorship"]["not_repairable"]
    assert adv["regime_stability"]["not_repairable"] and adv["regime_stability"]["repair"] == []
    assert "trial" in adv["cost_realism"]["note"] and adv["survivorship"]["note"] == ""
    assert integrity == "warn"


def test_mcp_suggest_fix_adds_advice_for_a_certificate(tmp_path: Path) -> None:
    src = tmp_path / "s.py"
    src.write_text("import numpy as np\n\n\ndef signal(df):\n    return np.ones(len(df))\n", encoding="utf-8")
    cert = tmp_path / "cert.json"
    cert.write_text(json.dumps({"schema": "strategy-verdict/1", "checks": [_row("cost_sensitivity")]}), encoding="utf-8")
    plain = suggest_fix(str(src))
    assert "advice" not in plain
    withc = suggest_fix(str(src), str(cert))
    assert withc["advice"][0]["check"] == "cost_sensitivity" and withc["advice"][0]["repair"]
