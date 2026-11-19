"""ARL, depth and the rules version are shown everywhere: certificates, recheck, CLI, HTML, dossier, MCP, Action, monitor."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.alpha import demo_panel, validate_alpha
from monte_neo.backtest import ExecutionModel, synthetic_ohlcv
from monte_neo.cli import readiness_cmd
from monte_neo.cli.entry import main as entry_main
from monte_neo.dossier.build import build_dossier
from monte_neo.dossier.html import render_dossier as render_html
from monte_neo.dossier.lite import render_lite
from monte_neo.mcp import tools
from monte_neo.readiness import arl_block, readiness
from monte_neo.verify import verify_strategy
from monte_neo.verify.fixes import advise_depth
from monte_neo.verify.recheck import recheck_certificate
from monte_neo.verify.report_html import render_html as render_verdict_html
from monte_neo.verify.sealed_holdout import SealedHoldout

ROOT = Path(__file__).resolve().parents[2]
DF = synthetic_ohlcv(900, seed=3)
MODEL = ExecutionModel(side_mode="long_short", warmup_bars=20)


def _sig(d: pd.DataFrame) -> np.ndarray:
    c = d["close"]
    return (c > c.rolling(30).mean()).astype(int).to_numpy()


@pytest.fixture(scope="module")
def cert() -> dict:
    return verify_strategy(DF, signal_fn=_sig, model=MODEL, n_trials=3)


def test_certificate_records_level_depth_and_rules_version(cert: dict) -> None:
    arl = cert["arl"]
    assert arl["rules_version"] == "arl-rules/1" and arl["provisional"] is True
    assert arl["headline"] == f"ARL {arl['level']}, depth {arl['depth']}/4 (arl-rules/1, provisional)"
    assert isinstance(arl["open_criteria"], list) and arl["summary"].startswith("ARL")
    assert any("ARL" in a and "of ARL" in a for a in cert["next_actions"]) or arl["level"] >= 8


def test_arl_is_not_part_of_the_certificate_id() -> None:
    a = verify_strategy(DF, signal_fn=_sig, model=MODEL, n_trials=3)
    b = verify_strategy(DF, signal_fn=_sig, model=MODEL, n_trials=3)
    assert a["certificate_id"] == b["certificate_id"] and a["arl"] == b["arl"]


def test_recheck_recomputes_with_the_recorded_version() -> None:
    cert = verify_strategy(DF, signals=_sig(DF), model=MODEL, n_trials=3)  # signals only, so the recheck sees the same evidence
    out = recheck_certificate(cert, DF, signals=_sig(DF))
    assert out["arl_rules_version"] == "arl-rules/1" and out["arl_matches"] is True and out["arl"].startswith("ARL")
    old = json.loads(json.dumps(cert))
    old["arl"]["rules_version"] = "arl-rules/0"
    bad = recheck_certificate(old, DF, signals=_sig(DF))
    assert bad["arl_matches"] is False and "unknown ARL rules version" in bad["arl_reason"]
    changed = json.loads(json.dumps(cert))
    changed["arl"]["level"] = 9
    assert recheck_certificate(changed, DF, signals=_sig(DF))["arl_matches"] is False
    legacy = {k: v for k, v in cert.items() if k != "arl"}
    assert "arl_matches" not in recheck_certificate(legacy, DF, signals=_sig(DF))


def test_verify_cli_html_and_action_show_the_headline(cert: dict, capsys: pytest.CaptureFixture[str]) -> None:
    from rich.console import Console

    from monte_neo.cli.verify_cmd import _render_text

    _render_text(cert, Console(width=200))
    assert cert["arl"]["headline"] in capsys.readouterr().out
    assert cert["arl"]["headline"] in render_verdict_html(cert)
    html = render_verdict_html({k: v for k, v in cert.items() if k != "arl"})
    assert "arl-rules" not in html
    assert "arl['headline']" in (ROOT / "action.yml").read_text(encoding="utf-8")


def test_readiness_cli_text_json_and_errors(cert: dict, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    c = tmp_path / "c.json"
    c.write_text(json.dumps(cert), encoding="utf-8")
    assert readiness_cmd.main(["--certificate", str(c), "--n-trials", "20"]) == 0
    out = capsys.readouterr().out
    assert "ARL" in out and "arl-rules/1" in out and "Rostyslav Shcherbyna" in out and "depth" in out
    assert readiness_cmd.main(["--certificate", str(c), "--format", "json"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["rules_version"] == "arl-rules/1" and rep["n_trials_used"] >= 3
    assert readiness_cmd.main([]) == 3
    assert readiness_cmd.main(["--certificate", str(tmp_path / "missing.json")]) == 3
    assert readiness_cmd.main(["--certificate", str(c), "--rules-version", "arl-rules/9"]) == 3
    assert readiness_cmd.main(["--bogus"]) == 3
    assert entry_main.__module__ == "monte_neo.cli.entry"


def test_readiness_cli_holdout_and_sync_docs(cert: dict, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    c = tmp_path / "c.json"
    c.write_text(json.dumps(cert), encoding="utf-8")
    h = SealedHoldout(tmp_path / "h.jsonl")
    h.freeze(DF, "def signal(df):\n    return df['close']\n")
    assert readiness_cmd.main(["--certificate", str(c), "--holdout", str(tmp_path / "h.jsonl")]) == 0
    capsys.readouterr()
    page = tmp_path / "p.md"
    page.write_text("x\n<!-- arl:levels:start -->\nstale\n<!-- arl:levels:end -->\n", encoding="utf-8")
    assert readiness_cmd.main(["--sync-docs", str(page)]) == 0
    assert "Idea on clean data" in page.read_text(encoding="utf-8") and "stale" not in page.read_text(encoding="utf-8")


def test_dispatch_through_the_entry_point(cert: dict, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    c = tmp_path / "c.json"
    c.write_text(json.dumps(cert), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["monte-neo", "readiness", "--certificate", str(c)])
    assert entry_main() == 0
    assert "depth" in capsys.readouterr().out


def test_alpha_report_and_dossier_show_it(cert: dict) -> None:
    prices, scores, _ = demo_panel(seed=1, n_symbols=12, n_days=300)
    rep = validate_alpha(prices, scores, placebos=20, n_trials=5)
    assert rep["readiness"]["headline"].startswith("ARL") and rep["readiness"]["rules_version"] == "arl-rules/1"
    assert rep["readiness"]["n_trials_used"] == 5
    d = build_dossier(cert, alpha=rep)
    assert d["readiness"]["headline"] in render_html(d) and "provisional" in render_html(d)
    assert "Rostyslav Shcherbyna" in render_html(d) and d["readiness"]["headline"] in render_lite(d)
    h = {"valid": True, "opens": 1, "reason": None, "checks": []}
    assert build_dossier(cert, holdout=h)["readiness"]["levels"][0]["depth_criteria"]


def test_monitor_report_carries_the_arl(cert: dict, tmp_path: Path) -> None:
    from monte_neo.verify.live import verify_live

    idx = pd.bdate_range("2024-01-01", periods=120)
    live = pd.Series(np.random.default_rng(0).normal(0.0005, 0.01, 120), idx, name="return")
    rep = verify_live(cert, live, source="paper")
    assert rep["arl"]["headline"].startswith("ARL") and rep["arl"]["rules_version"] == "arl-rules/1"
    assert rep["metrics"]["live_span_days"] > 100 and rep["metrics"]["custody"] is None
    again = verify_live(cert, live, source="real_fills", custody="stmt-1")
    assert again["metrics"]["custody"] == "stmt-1"


def test_mcp_tools(cert: dict, tmp_path: Path) -> None:
    c = tmp_path / "c.json"
    c.write_text(json.dumps(cert), encoding="utf-8")
    out = tools.readiness_level(str(c), n_trials=10)
    assert out["rules_version"] == "arl-rules/1" and out["headline"].startswith("ARL")
    h = SealedHoldout(tmp_path / "h.jsonl")
    h.freeze(DF, "def signal(df):\n    return df['close']\n")
    assert tools.readiness_level(str(c), holdout_path=str(tmp_path / "h.jsonl"))["levels"]
    assert tools.readiness_level.__name__ in {t.__name__ for t in tools.TOOLS}
    src = tmp_path / "s.py"
    src.write_text("def signal(df):\n    return df['close'] > 0\n", encoding="utf-8")
    fix = tools.suggest_fix(str(src), str(c))
    assert "depth_advice" in fix and isinstance(fix["depth_advice"], list)


def test_depth_advice_has_commands_and_repairs_without_fitting() -> None:
    rep = readiness({"checks": [{"id": "data_integrity", "status": "pass", "category": "integrity"},
                                {"id": "cost_margin", "status": "pass", "category": "economics", "details": {"breakeven_bps": 12.0}},
                                {"id": "costs_modeled", "status": "pass", "category": "economics", "details": {"per_side_cost_bps": 10.0}},
                                {"id": "lookahead_truncation", "status": "pass", "category": "lookahead"},
                                {"id": "net_profitability", "status": "pass", "category": "economics"}],
                     "metrics": {}, "reproducibility": {"n_trials": 1}})
    assert rep["level"] == 3
    advice = advise_depth(rep)
    unmet = [a for a in advice if a["state"] == "unmet"]
    assert any(a["criterion"] == "D1" and a["level"] == 3 and a["repair"] and "n_trials grows" in a["note"] for a in unmet)  # R5: trade less
    for a in advice:
        assert a["command"]
        if a["state"] == "not assessed":
            assert a["repair"] == []  # no evidence is never "repaired"
    assert arl_block(rep)["open_criteria"]
