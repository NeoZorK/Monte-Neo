"""Extended dossier: sections, honest 'not provided', evidence-map wording, HTML snapshot, CLI."""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli.dossier_cmd import main
from monte_neo.dossier import build_dossier
from monte_neo.dossier.extended import EVIDENCE_STATEMENT, build_extended
from monte_neo.dossier.html import render_dossier
from monte_neo.verify import verify_strategy


@pytest.fixture(scope="module")
def certs():
    df = synthetic_ohlcv(1200, seed=21)
    a = json.loads(json.dumps(verify_strategy(df, signals=np.sign(df["close"].pct_change(20).fillna(0).to_numpy()), n_trials=12, probe_checks=4, profile="trend_cta"), default=str))
    b = json.loads(json.dumps(verify_strategy(df, signals=np.sign(df["close"].pct_change(40).fillna(0).to_numpy()), n_trials=30, probe_checks=4), default=str))
    return a, b


def test_sections_and_not_provided(certs) -> None:
    ext = build_extended(list(certs))
    assert ext["schema"] == "extended-dossier/1" and len(ext["strategies"]) == 2
    assert set(ext["not_provided"]) == {"search funnel", "portfolio", "monitoring"}
    s = ext["strategies"][0]
    assert s["arl"]["headline"].startswith("ARL") and s["profile"] == "trend_cta" and len(s["levels"]) == 9
    assert all("depth" in lv for lv in s["levels"]) and {r["id"] for r in s["costs"]} >= {"cost_sensitivity"}
    assert ext["search"]["n_trials_max"] == 30
    assert "not a compliance" in ext["evidence_map"]["statement"] and ext["evidence_map"]["statement"] == EVIDENCE_STATEMENT


def test_funnel_portfolio_and_monitoring_are_embedded(certs) -> None:
    funnel = {"stages": [{"stage": "variants tried on discovery", "count": 40}], "search_cost": {"expected_max_sharpe": 1.2}}
    pf = {"verdict": "REJECT", "checks": [{"id": "tail_dependence", "status": "fail", "summary": "x"}]}
    ext = build_extended(list(certs), funnel=funnel, portfolio=pf, live={"verdict": "PASS", "checks": []}, framework="ss1-23")
    assert ext["not_provided"] == [] and ext["portfolio"]["checks"][0]["id"] == "tail_dependence"
    assert ext["evidence_map"]["clauses"]


def test_empty_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        build_extended([])


def test_html_snapshot_structure_is_stable(certs) -> None:
    d = build_dossier(certs[0], framework="sr11-7", meta={"name": "Snap"})
    d["extended"] = build_extended(list(certs), funnel={"stages": [{"stage": "tried", "count": 5}], "search_cost": None})
    html = render_dossier(d)
    heads = re.findall(r"<h2>(.*?)</h2>", re.sub(r"<span[^>]*>|</span>", "", html))
    skeleton = [re.sub(r"[0-9a-f]{16}", "ID", h) for h in heads]
    assert skeleton[0] == "Alpha Readiness Level" or "Search: funnel and cost" in skeleton
    for needed in ("Search: funnel and cost", "Portfolio", "Monitoring", "Framework map", "Sign-off"):
        assert needed in skeleton
    assert skeleton.index("Search: funnel and cost") < skeleton.index("Framework map")
    assert "Not provided" in html and "<script" not in html.lower()
    assert "Depth D1 to D4, with reasons" in html and "Coverage means evidence in this dossier, not compliance" in html


def test_cli_extended_end_to_end(tmp_path, certs) -> None:
    c1, c2 = tmp_path / "a.json", tmp_path / "b.json"
    c1.write_text(json.dumps(certs[0]))
    c2.write_text(json.dumps(certs[1]))
    out = tmp_path / "d"
    assert main(["--certificate", str(c1), "--also", str(c2), "--out", str(out), "--name", "X"]) == 0
    doc = json.loads((out / "dossier.json").read_text())
    assert doc["extended"]["schema"] == "extended-dossier/1"
    assert "Search: funnel and cost" in (out / "dossier.html").read_text()
    assert main(["--certificate", str(c1), "--also", str(tmp_path / "missing.json"), "--out", str(tmp_path / "e")]) == 3
