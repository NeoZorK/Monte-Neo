"""Search statistics, the report, the diagnosis, the anti-patterns and the whole pipeline end to end."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from monte_neo.research import ResearchProject
from monte_neo.research.diagnosis import ORDER, diagnose, years_needed
from monte_neo.research.report import (
    REPORT_SCHEMA,
    _screened_effective,
    antipatterns,
    build_report,
    render_html,
    render_text,
    report_schema,
    write_report,
)
from monte_neo.research.search_stats import (
    bh_qvalues,
    effective_trials,
    min_detectable_sharpe,
    one_sided_p,
    power_row,
    search_statistics,
    storey_pi0,
    storey_qvalues,
)
from monte_neo.research.service import run_action

N = 900
SOURCE = ("import numpy as np\n\ndef signal(df, n=20, side=1):\n    c = df['close'].to_numpy()\n    ma = np.convolve(c, np.ones(n) / n, mode='full')[:len(c)]\n"
          "    s = np.where(c > ma, side, -side)\n    s[:n] = 0\n    return s\n")
GRAMMAR = f"SOURCE = {SOURCE!r}\nGRID = {{'n': [5, 10, 20, 40], 'side': [1, -1]}}\nLABEL = 'ma'\n"


def _df(drift: float, seed: int = 3, n: int = N) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(drift, 0.01, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame({"timestamp": pd.bdate_range("2018-01-01", periods=n, tz="UTC"), "open": open_, "high": np.maximum(open_, close) * 1.002,
                         "low": np.minimum(open_, close) * 0.998, "close": close, "volume": 1000.0})


def _project(tmp_path, drift: float, *, profile=None, batches=((3,),)):
    tmp_path.mkdir(parents=True, exist_ok=True)
    df = _df(drift)
    csv, g = tmp_path / "d.csv", tmp_path / "g.py"
    df.to_csv(csv, index=False)
    g.write_text(GRAMMAR)
    root = tmp_path / "p"
    ts = df["timestamp"]
    run_action(root, "init", data=csv, discovery_end=str(ts.iloc[500]), validation_end=str(ts.iloc[750]), name="r", grammar=g, profile=profile)
    run_action(root, "screen")
    for (k,) in batches:
        run_action(root, "promote", top=k, min_sharpe=-1e9)
        run_action(root, "validate")
    return ResearchProject(root)


# ---------------------------------------------------------------- search statistics
def test_fdr_qvalues() -> None:
    p = np.array([0.01, 0.04, 0.03, 0.005])
    q = bh_qvalues(p)
    assert q == pytest.approx([0.02, 0.04, 0.04, 0.02]) and (q >= p).all()
    assert bh_qvalues(np.array([])).size == 0 and bh_qvalues(np.array([0.5]))[0] == 0.5
    assert storey_pi0(p) == 1.0  # fewer than 20 tests: no estimate, Benjamini-Hochberg stands
    uniform = np.linspace(0.001, 0.999, 200)
    mostly_signal = np.concatenate([np.full(150, 1e-4), np.linspace(0.01, 0.99, 50)])
    assert storey_pi0(uniform) > 0.9 and storey_pi0(mostly_signal) < 0.4
    assert (storey_qvalues(mostly_signal) <= bh_qvalues(mostly_signal) + 1e-12).all()
    assert one_sided_p(np.array([-3.0, 0.0, 3.0])).tolist() == sorted(one_sided_p(np.array([-3.0, 0.0, 3.0])).tolist(), reverse=True)


def test_effective_trials_counts_ideas_not_copies() -> None:
    rng = np.random.default_rng(0)
    base = rng.normal(0, 0.01, 400)
    copies = np.vstack([base + rng.normal(0, 1e-4, 400) for _ in range(5)])
    other = rng.normal(0, 0.01, (3, 400))
    e = effective_trials(np.vstack([copies, other]), 0.95)
    assert e["n"] == 8 and e["n_clusters"] == 4 and e["n_eff"] >= 4 and e["n_eff"] <= 8
    assert effective_trials(copies, 0.95)["n_clusters"] == 1
    assert effective_trials(other, 0.95)["n_eff"] == 3
    solo = effective_trials(base.reshape(1, -1))
    assert solo["n_eff"] == 1 and effective_trials(np.vstack([base, base])[:, :5])["n_eff"] == 2  # too short to tell: nothing is merged
    flat = np.vstack([np.zeros(100), rng.normal(0, 1, 100), rng.normal(0, 1, 100)])
    assert effective_trials(flat)["n_eff"] == 3  # a series without variance is counted as its own try
    with pytest.raises(ValueError, match="candidates, bars"):
        effective_trials(np.zeros(5))


def test_minimum_detectable_sharpe_grows_with_tries_and_shrinks_with_history() -> None:
    a = min_detectable_sharpe(1, 1000, 252)["min_detectable_sharpe_annual"]
    b = min_detectable_sharpe(100, 1000, 252)["min_detectable_sharpe_annual"]
    c = min_detectable_sharpe(100, 4000, 252)["min_detectable_sharpe_annual"]
    assert a < b and c < b and min_detectable_sharpe(0, 1, 252)["n_trials"] == 1
    assert power_row(3, 5000, 252)["status"] == "pass" and power_row(500, 250, 252)["status"] == "warn"
    assert "detect an annual Sharpe" in power_row(3, 5000, 252)["summary"]


def test_search_statistics_finds_a_planted_edge_and_checks_shapes() -> None:
    rng = np.random.default_rng(1)
    r = np.vstack([rng.normal(0, 0.01, (24, 500)), rng.normal(0.003, 0.01, (1, 500))])
    st = search_statistics(r, [f"c{i}" for i in range(25)], 252.0)
    assert st["fdr_discoveries"] == ["c24"] and st["effective_trials"]["n_eff"] <= 25 and st["detectable_effective"]["n_trials"] <= 25
    assert all(0 <= c["cluster"] < 25 for c in st["candidates"])
    with pytest.raises(ValueError, match="one id per row"):
        search_statistics(r, ["a"], 252.0)


# ---------------------------------------------------------------- diagnosis
def test_diagnosis_groups_and_next_actions_add_information_not_variants() -> None:
    facts = {"n_trials": 50, "spa_passes": False, "years": 2.0, "best_sharpe_annual": 0.6, "min_detectable_sharpe_annual": 1.9, "any_beats_null": False, "any_significant": False}
    cert = {c: {"id": c, "status": s} for c, s in (("lookahead_truncation", "fail"), ("net_profitability", "fail"), ("alpha_after_beta", "warn"), ("regime_stability", "warn"),
                                                    ("capacity", "warn"), ("survivorship", "warn"), ("sample_size", "fail"), ("data_integrity", "warn"))}
    d = diagnose(facts, [{"id": "c1", "checks": cert}, {"id": "c2"}])
    ids = [g["id"] for g in d["groups"]]
    assert ids == [g for g in ORDER if g in ids] and set(ids) == set(ORDER) and not d["passed"]
    impl = next(g for g in d["groups"] if g["id"] == "implementation")
    assert all("fail" in e for e in impl["evidence"]) and not any("data_integrity" in e for e in impl["evidence"])  # a warning is not a defect
    text = " ".join(d["next_actions"]).lower()
    assert "do not add variants" in text and "new window" in text and "tune" not in text.replace("re-tune the rule to the costs", "")
    assert any("years would be needed" in e for g in d["groups"] for e in g["evidence"])
    clean = diagnose({"n_trials": 1, "spa_passes": True, "years": 5.0, "best_sharpe_annual": 2.0, "min_detectable_sharpe_annual": 0.5, "any_beats_null": True, "any_significant": True}, [])
    assert clean["passed"] and clean["groups"] == [] and clean["next_actions"] == []
    assert years_needed(-1.0, 10) is None and years_needed(1.0, 10) > years_needed(2.0, 10)


# ---------------------------------------------------------------- report on a project
def test_report_of_a_losing_search_explains_why_and_validates_against_the_schema(tmp_path) -> None:
    p = _project(tmp_path, 0.0, profile="trend_cta")
    rep = build_report(p, certify=1)
    sch = report_schema()
    assert rep["schema"] == REPORT_SCHEMA == sch["title"] and set(sch["required"]) <= set(rep)
    for key, spec in sch["properties"].items():
        for req in spec.get("required", []):
            if isinstance(rep[key], dict):
                assert req in rep[key]
    assert rep["project"]["profile"] == "trend_cta" and rep["funnel"]["n_trials"] == 3 and rep["search"]["n_screened"] == 8 and "detectable" in rep["search"]
    assert rep["search"]["screened_effective"]["screened"] == 8 and rep["champion"] is None
    certified = [c for c in rep["candidates"] if c["arl"]]
    assert len(certified) == 1 and certified[0]["arl"]["headline"].startswith("ARL") and certified[0]["profile"]["id"] == "trend_cta" and certified[0]["certificate_id"]
    assert rep["diagnosis"]["groups"] and not rep["diagnosis"]["passed"] and rep["disclaimer"]
    json.dumps(rep, default=str)  # machine readable
    text, page = render_text(rep), render_html(rep)
    assert "Search funnel" in text and "<html" in page and "Research report: r" in page and "No champion" in page
    again = build_report(p)  # the certificate is stored: no second run needed
    assert [c["arl"] is not None for c in again["candidates"]].count(True) == 1


def test_write_report_files_and_stage(tmp_path) -> None:
    p = _project(tmp_path, 0.0)
    out = tmp_path / "out"
    write_report(p, out=out)
    assert json.loads((out / "report.json").read_text())["schema"] == REPORT_SCHEMA and "<html" in (out / "report.html").read_text()
    assert ResearchProject(tmp_path / "p").manifest["stage"] == "reported"
    inplace = run_action(tmp_path / "p", "report")
    assert (tmp_path / "p" / "report.json").exists() and inplace["schema"] == REPORT_SCHEMA and "Search funnel" in inplace["text"]


def test_report_before_validation_points_to_the_next_step(tmp_path) -> None:
    df = _df(0.0)
    df.to_csv(tmp_path / "d.csv", index=False)
    ResearchProject.create(tmp_path / "e", df, df["timestamp"].iloc[500], df["timestamp"].iloc[750])
    rep = build_report(ResearchProject(tmp_path / "e"))
    assert rep["candidates"] == [] and rep["search"]["n_trials"] == 1 and "Screen candidates" in rep["diagnosis"]["next_actions"][0]
    assert "tries:" not in render_text(rep) and "No champion" in render_html(rep)
    assert _screened_effective(ResearchProject(tmp_path / "e"), 0.95) is None


def test_a_real_edge_gives_a_champion_that_is_frozen_then_handed_over(tmp_path) -> None:
    p = _project(tmp_path, 0.004, profile="trend_cta")
    rep = build_report(p)
    assert rep["candidates"][0]["gate_open"] and rep["champion"]["frozen"] is False and rep["diagnosis"]["passed"]
    assert "Freeze the champion" in rep["diagnosis"]["next_actions"][0] and "not frozen" in render_html(rep)
    cid = rep["candidates"][0]["id"]
    run_action(tmp_path / "p", "holdout", candidate=cid, confirm=True)
    run_action(tmp_path / "p", "certify")
    done = build_report(ResearchProject(tmp_path / "p"))
    assert done["champion"]["frozen"] is True and done["champion"]["holdout"]["valid"] and done["champion"]["final_arl"]["headline"].startswith("ARL") and "frozen" in render_html(done)
    assert done["candidates"][0]["arl"] and done["candidates"][0]["profile"]["id"] == "trend_cta"
    out = run_action(tmp_path / "p", "handoff", dossier_dir=tmp_path / "dossier", hall_dir=tmp_path / "hall", author="A. Person", name="demo trend", category="trend")
    assert out["certificate_id"] and (tmp_path / "dossier").is_dir() and out["hall"]["entry"]


# ---------------------------------------------------------------- anti-patterns
def test_many_batches_on_one_window_are_flagged_with_rising_severity(tmp_path) -> None:
    two = _project(tmp_path, 0.0, batches=((2,), (2,)))
    a = {x["id"]: x for x in antipatterns(two)}
    assert a["n_grew_without_new_information"]["severity"] == "medium" and "from 2 to 4" in a["n_grew_without_new_information"]["text"]
    four = _project(tmp_path / "x", 0.0, batches=((2,), (2,), (2,), (2,)))
    assert {x["id"]: x for x in antipatterns(four)}["n_grew_without_new_information"]["severity"] == "high"
    one = _project(tmp_path / "y", 0.0)
    assert not antipatterns(one) and {"search_cannot_detect"} == {x["id"] for x in antipatterns(one, {"detectable": {"min_detectable_sharpe_annual": 3.0, "n_trials": 9}})}


# ---------------------------------------------------------------- CLI and dry run
def test_dry_run_runs_the_whole_pipeline_and_finds_nothing(tmp_path, capsys) -> None:
    from monte_neo.cli.research_cmd import main

    root = tmp_path / "demo"
    assert main(["init", "--dry-run", "--project", str(root)]) == 0
    out = capsys.readouterr().out
    assert "Search funnel" in out and "candidates" in out
    assert (root / "report.html").exists() and (root / "grammar.py").exists() and (root / "demo_data.csv").exists()
    st = run_action(root, "status")
    assert st["stage"] == "reported" and st["n_screened"] == 16 and st["n_trials"] == 3 and not st["frozen"]
    rep = json.loads((root / "report.json").read_text())
    assert rep["candidates"] and not any(c["gate_open"] for c in rep["candidates"])  # a random walk has nothing to find
    assert main(["init", "--dry-run", "--project", str(root)]) == 3  # a project folder is fixed once
    capsys.readouterr()
    again = run_action(tmp_path / "demo2", "init", dry_run=True, profile="trend_cta")
    assert again["dry_run"] is True and again["steps"] == ["init", "screen", "promote", "validate"] and "synthetic" in again["note"]


def test_cli_status_report_handoff_and_errors(tmp_path, capsys) -> None:
    from monte_neo.cli.research_cmd import main

    p = _project(tmp_path, 0.004)
    base = ["--project", str(tmp_path / "p")]
    assert main(["status", *base]) == 0 and "project r" in capsys.readouterr().out
    assert main(["status", *base, "--format", "json"]) == 0 and json.loads(capsys.readouterr().out)["stage"] == "validated"
    assert main(["report", *base, "--certify-top", "1", "--out", str(tmp_path / "o")]) == 0 and "Search funnel" in capsys.readouterr().out
    assert (tmp_path / "o" / "report.html").exists()
    assert main(["handoff", *base, "--dossier", str(tmp_path / "d")]) == 3  # nothing frozen yet
    assert main(["holdout", *base, "--candidate", p._validated()[0]]) == 3  # no --confirm
    assert main(["promote", *base]) == 3 and main(["status", "--project", str(tmp_path / "missing")]) == 3
    capsys.readouterr()
    assert main(["init", *base, "--grammar", str(tmp_path / "g.py")]) == 3


# ---------------------------------------------------------------- end to end through the command line
def test_end_to_end_cli_from_init_to_forward_and_handoff(tmp_path, capsys) -> None:
    from monte_neo.cli.research_cmd import main

    df = _df(0.004)
    csv, g = tmp_path / "d.csv", tmp_path / "g.py"
    df.to_csv(csv, index=False)
    g.write_text(GRAMMAR)
    ts = df["timestamp"]
    proj = ["--project", str(tmp_path / "e2e")]
    assert main(["init", *proj, "--data", str(csv), "--discovery-end", str(ts.iloc[500]), "--validation-end", str(ts.iloc[750]), "--grammar", str(g), "--profile", "trend_cta", "--name", "e2e"]) == 0
    assert main(["screen", *proj, "--chunk", "3"]) == 0 and main(["promote", *proj, "--top", "3", "--min-sharpe=-1e9"]) == 0 and main(["validate", *proj]) == 0
    capsys.readouterr()
    assert main(["report", *proj, "--format", "json", "--certify-top", "2"]) == 0
    rep = json.loads(capsys.readouterr().out)
    champion = rep["candidates"][0]
    assert champion["gate_open"] and rep["schema"] == REPORT_SCHEMA and champion["arl"]["headline"].startswith("ARL")
    assert main(["holdout", *proj, "--candidate", champion["id"], "--confirm"]) == 0
    assert main(["certify", *proj]) == 0 and main(["forward", "freeze", *proj]) == 0
    longer = df.copy()
    extra = _df(0.004, seed=9, n=N + 20).iloc[N:]
    longer = pd.concat([df, extra.assign(timestamp=pd.bdate_range(df["timestamp"].iloc[-1] + pd.offsets.BDay(1), periods=20, tz="UTC"))], ignore_index=True)
    longer.to_csv(tmp_path / "longer.csv", index=False)
    capsys.readouterr()
    assert main(["forward", "record", *proj, "--data", str(tmp_path / "longer.csv"), "--format", "json"]) == 0 and json.loads(capsys.readouterr().out)["new"] == 20
    assert main(["handoff", *proj, "--dossier", str(tmp_path / "dossier"), "--hall", str(tmp_path / "hall"), "--author", "A. Person", "--name", "e2e rule", "--category", "trend"]) == 0
    capsys.readouterr()
    assert main(["status", *proj, "--format", "json"]) == 0
    st = json.loads(capsys.readouterr().out)
    assert st["frozen"] == champion["id"] and st["holdout_opens"] == 1 and st["chain_ok"] and st["stage"] == "reported"
    assert main(["holdout", *proj, "--confirm"]) == 0  # a second opening is allowed to run and spoils the holdout, loudly
    assert "holdout_spoiled" in {w["id"] for w in run_action(tmp_path / "e2e", "status")["warnings"]}
