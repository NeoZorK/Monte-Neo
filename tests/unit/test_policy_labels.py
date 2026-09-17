"""Research label JSONL logger tests."""

from __future__ import annotations

from monte_neo.policy import LABEL_SCHEMA, HeuristicPolicy, append_research_label, build_research_state


def test_append_research_label(tmp_path):
    path = tmp_path / "labels.jsonl"
    report = {
        "metrics": {
            "promote_ok": True,
            "next_action": "promote_paper_oms",
            "overfit_risk": "med",
            "promote_mode": "holdout_positive",
            "gap_best": 0.1,
            "mean_gap_top_k": 0.08,
        },
        "train": {"best_return": 0.2, "best_pair": {"fast": 5, "slow": 30}},
        "holdout": {"at_train_best": 0.1},
        "split": {"n_bars": 1000},
    }
    export = {
        "ok": True,
        "device": "cpu_numba",
        "bars": 1000,
        "combos": 2,
        "export_api_version": "1",
        "engine": "t",
        "lane": "research_bar",
        "model": {},
        "work_checklist": {
            "next_bar_fill": True,
            "fees": True,
            "no_lookahead": True,
            "cash_position_equity": True,
        },
        "timing": {},
        "metrics": {
            "best_return": 0.2,
            "rows": [
                {"fast": 5, "slow": 30, "total_return": 0.2},
                {"fast": 6, "slow": 31, "total_return": 0.15},
            ],
        },
    }
    decision = HeuristicPolicy().decide(build_research_state(export, holdout_report=report))
    rec = append_research_label(
        path, holdout_report=report, decision=decision, human_label="accept", notes="unit"
    )
    assert rec["schema"] == LABEL_SCHEMA
    assert path.read_text(encoding="utf-8").count("\n") == 1
    append_research_label(path, holdout_report=report, human_label="reject")
    assert path.read_text(encoding="utf-8").count("\n") == 2


def test_policy_holdout_unlocks_promote():
    report = {
        "metrics": {
            "gap_best": 0.4,
            "mean_gap_top_k": 0.3,
            "overfit_risk": "high",
            "promote_ok": True,
            "next_action": "promote_paper_oms",
        },
        "holdout": {"at_train_best": 0.05},
    }
    export = {
        "ok": True,
        "device": "cpu_numba",
        "bars": 2000,
        "combos": 2,
        "export_api_version": "1",
        "engine": "t",
        "lane": "research_bar",
        "model": {},
        "work_checklist": {
            "next_bar_fill": True,
            "fees": True,
            "no_lookahead": True,
            "cash_position_equity": True,
        },
        "timing": {},
        "metrics": {
            "best_return": 0.02,  # below default promote threshold 0.05
            "rows": [
                {"fast": 5, "slow": 30, "total_return": 0.02},
                {"fast": 6, "slow": 31, "total_return": 0.01},
            ],
        },
    }
    d = HeuristicPolicy().decide(build_research_state(export, holdout_report=report))
    assert d["promote_to_paper_oms"] is True
    assert d["next_action"] == "promote_paper_oms"
    assert d["worth_mc_stress"] is True


def test_append_with_extra(tmp_path):
    path = tmp_path / "x.jsonl"
    append_research_label(path, extra={"seed": 1})
    assert '"seed": 1' in path.read_text(encoding="utf-8")
