"""HeuristicPolicy / ResearchState unit tests."""

from __future__ import annotations

from monte_neo.policy import HeuristicPolicy, PolicyConfig, build_research_state, triage_export


def _fake_export(*, returns: list[float], checklist: dict | None = None, ok: bool = True, **extra) -> dict:
    rows = []
    for i, r in enumerate(returns):
        rows.append({"fast": 5, "slow": 30 + i, "total_return": r})
    out = {
        "ok": ok,
        "device": "cpu_numba",
        "fallback_reason": extra.get("fallback_reason"),
        "bars": 50_000,
        "combos": len(returns),
        "export_api_version": "1",
        "engine": "test",
        "lane": "research_bar",
        "model": {"commission_bps": 5.0, "slippage_bps": 5.0, "warmup_bars": 50},
        "work_checklist": checklist
        or {
            "next_bar_fill": True,
            "fees": True,
            "no_lookahead": True,
            "cash_position_equity": True,
        },
        "timing": {"elapsed_s": 0.2},
        "metrics": {"best_return": max(returns) if returns else None, "rows": rows},
    }
    if "memory" in extra:
        out["memory"] = extra["memory"]
    return out


def test_build_research_state_summary():
    state = build_research_state(_fake_export(returns=[0.1, -0.05, 0.2]), run_id="r1")
    assert state["schema"] == "mn.research_state.v1"
    assert state["run_id"] == "r1"
    assert state["metrics"]["n_rows"] == 3
    assert state["metrics"]["best_return"] == 0.2
    assert 0.0 <= state["metrics"]["frac_positive"] <= 1.0
    assert "open" not in state and "close" not in state


def test_build_research_state_empty_rows():
    exp = _fake_export(returns=[])
    exp["metrics"] = {"best_return": 0.42, "rows": []}
    state = build_research_state(exp)
    assert state["metrics"]["n_rows"] == 0
    assert state["metrics"]["best_return"] == 0.42
    assert state["metrics"]["frac_positive"] is None


def test_build_research_state_empty_no_best():
    exp = _fake_export(returns=[])
    exp["metrics"] = {"rows": []}
    state = build_research_state(exp)
    assert state["metrics"]["best_return"] is None


def test_policy_config_to_dict():
    d = PolicyConfig().to_dict()
    assert "t_promote_return" in d
    assert d["top_k"] == 5


def test_triage_promote():
    rets = [0.12, 0.11, 0.10, 0.09, 0.08] + [-0.01] * 5
    out = triage_export(_fake_export(returns=rets), config=PolicyConfig(t_promote_return=0.05))
    d = out["decision"]
    assert d["backend"] == "heuristic"
    assert d["promote_to_paper_oms"] is True
    assert d["next_action"] == "promote_paper_oms"
    assert d["worth_mc_stress"] is True


def test_triage_checklist_blocks_promote():
    rets = [0.5, 0.4, 0.3]
    exp = _fake_export(
        returns=rets,
        checklist={
            "next_bar_fill": False,
            "fees": True,
            "no_lookahead": True,
            "cash_position_equity": True,
        },
    )
    d = triage_export(exp)["decision"]
    assert d["promote_to_paper_oms"] is False
    assert d["next_action"] == "export_golden"
    assert d["overfit_risk"] == "high"


def test_triage_reject_low_return():
    d = triage_export(_fake_export(returns=[-0.2, -0.1, -0.05]), config=PolicyConfig(t_min_return=0.0))[
        "decision"
    ]
    assert d["next_action"] in {"reject", "stop"}
    assert d["promote_to_paper_oms"] is False


def test_triage_ok_false():
    d = triage_export(_fake_export(returns=[0.5], ok=False))["decision"]
    assert d["next_action"] == "reject"
    assert d["confidence"] >= 0.9


def test_triage_no_best_return():
    exp = _fake_export(returns=[])
    exp["metrics"] = {"rows": [{"fast": 1, "slow": 2}]}  # missing total_return → 0.0
    # Force None best via empty metrics path after state build with n_rows>0 but decide with best None:
    state = build_research_state(exp)
    state["metrics"]["best_return"] = None
    d = HeuristicPolicy().decide(state)
    assert d["next_action"] == "stop"


def test_triage_low_frac_positive():
    # one positive spike, many negatives → low frac
    rets = [0.2] + [-0.05] * 20
    d = triage_export(
        _fake_export(returns=rets),
        config=PolicyConfig(t_min_return=-1.0, p_min_frac_positive=0.5),
    )["decision"]
    assert d["next_action"] == "stop"
    assert d["overfit_risk"] == "med"


def test_triage_lone_peak_run_mc():
    # best high, edge huge, top rows NOT clustered (spread fast/slow)
    rows = [
        {"fast": 5, "slow": 50, "total_return": 0.4},
        {"fast": 20, "slow": 200, "total_return": 0.01},
        {"fast": 30, "slow": 300, "total_return": 0.0},
        {"fast": 40, "slow": 400, "total_return": -0.01},
        {"fast": 50, "slow": 500, "total_return": -0.02},
    ]
    exp = _fake_export(returns=[r["total_return"] for r in rows])
    exp["metrics"]["rows"] = rows
    d = triage_export(exp, config=PolicyConfig(t_promote_return=0.5, e_hi_edge=0.1))["decision"]
    assert d["next_action"] == "run_mc"
    assert d["overfit_risk"] == "high"
    assert d["worth_mc_stress"] is True
    assert d["promote_to_paper_oms"] is False


def test_triage_refine_grid_cluster():
    # clustered but below promote
    rets = [0.03, 0.029, 0.028, 0.027, 0.026]
    d = triage_export(
        _fake_export(returns=rets),
        config=PolicyConfig(t_promote_return=0.5, t_min_return=0.0),
    )["decision"]
    assert d["next_action"] == "refine_grid"


def test_triage_decent_stop():
    # not clustered (far params), below promote, above min
    rows = [
        {"fast": 5, "slow": 50, "total_return": 0.02},
        {"fast": 50, "slow": 200, "total_return": 0.01},
    ]
    exp = _fake_export(returns=[0.02, 0.01])
    exp["metrics"]["rows"] = rows
    d = triage_export(
        exp,
        config=PolicyConfig(t_promote_return=0.5, e_hi_edge=10.0, t_min_return=0.0),
    )["decision"]
    assert d["next_action"] == "stop"
    assert "below promote" in " ".join(d["reasons"])


def test_triage_fallback_reason_and_zero_std():
    # identical returns → near-zero std → reject
    rets = [0.05, 0.05, 0.05, 0.05]
    d = triage_export(
        _fake_export(returns=rets, fallback_reason="metal_max_bars_exceeded"),
        config=PolicyConfig(t_promote_return=0.01),
    )["decision"]
    assert d["next_action"] == "reject"
    assert d["overfit_risk"] == "high"
    assert any("fallback" in r for r in d["reasons"])


def test_checklist_empty_ok():
    exp = _fake_export(returns=[0.2, 0.19, 0.18, 0.17, 0.16])
    exp["work_checklist"] = {}
    d = triage_export(exp, config=PolicyConfig(t_promote_return=0.05))["decision"]
    assert d["promote_to_paper_oms"] is True


def test_top_cluster_short():
    # single top row → cluster false → may stop/promote depending
    d = triage_export(
        _fake_export(returns=[0.02]),
        config=PolicyConfig(t_promote_return=0.5, e_hi_edge=10.0),
    )["decision"]
    assert d["next_action"] == "stop"


def test_heuristic_policy_direct():
    state = build_research_state(_fake_export(returns=[0.01, 0.02]))
    d = HeuristicPolicy(PolicyConfig(t_promote_return=0.5)).decide(state)
    assert d["next_action"] in {"stop", "refine_grid", "reject"}
