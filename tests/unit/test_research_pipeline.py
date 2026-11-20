"""Research as a working pipeline: manifest, lock, resume, grammar plugin, pre-registration traps, status, forward journal, hand-off."""

from __future__ import annotations

import json
import os
from pathlib import Path as Path_

import numpy as np
import pandas as pd
import pytest

from monte_neo.research import ResearchProject
from monte_neo.research.forward import MAX_BARS_PER_RUN, ForwardJournal
from monte_neo.research.grammar import DEMO_GRID, MAX_VARIANTS, demo_grammar, load_grammar
from monte_neo.research.handoff import handoff
from monte_neo.research.manifest import (
    DEFAULT_POLICY,
    ProjectLock,
    atomic_write,
    new_manifest,
    read_manifest,
    write_manifest,
)
from monte_neo.research.project import list_sha
from monte_neo.research.service import run_action
from monte_neo.research.status import project_status, status_text

N = 900
SOURCE = ("import numpy as np\n\ndef signal(df, n=20, side=1):\n    c = df['close'].to_numpy()\n    ma = np.convolve(c, np.ones(n) / n, mode='full')[:len(c)]\n"
          "    s = np.where(c > ma, side, -side)\n    s[:n] = 0\n    return s\n")
GRAMMAR = f"SOURCE = {SOURCE!r}\nGRID = {{'n': [5, 10, 20, 40], 'side': [1, -1]}}\nLABEL = 'ma'\n"


def _df(n: int = N, drift: float = 0.0006, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(drift, 0.01, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame({"timestamp": pd.bdate_range("2018-01-01", periods=n, tz="UTC"), "open": open_, "high": np.maximum(open_, close) * 1.002,
                         "low": np.minimum(open_, close) * 0.998, "close": close, "volume": 1000.0})


DF = _df()
TS = DF["timestamp"]


@pytest.fixture
def csv(tmp_path):
    f = tmp_path / "d.csv"
    DF.to_csv(f, index=False)
    return f


@pytest.fixture
def gfile(tmp_path):
    f = tmp_path / "g.py"
    f.write_text(GRAMMAR)
    return f


def _init(tmp_path, csv, gfile, **kw):
    return run_action(tmp_path / "p", "init", data=csv, discovery_end=str(TS.iloc[500]), validation_end=str(TS.iloc[750]), name="t", grammar=gfile, **kw)


def _through_validate(tmp_path, csv, gfile, top=3):
    _init(tmp_path, csv, gfile)
    run_action(tmp_path / "p", "screen")
    run_action(tmp_path / "p", "promote", top=top, min_sharpe=-1e9)
    run_action(tmp_path / "p", "validate")
    return ResearchProject(tmp_path / "p")


# ---------------------------------------------------------------- manifest, atomic write, lock
def test_atomic_write_replaces_and_cleans_up(tmp_path, monkeypatch) -> None:
    f = tmp_path / "x" / "a.json"
    atomic_write(f, "one")
    atomic_write(f, "two")
    assert f.read_text() == "two" and [p.name for p in f.parent.iterdir()] == ["a.json"]

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        atomic_write(f, "three")
    assert f.read_text() == "two" and [p.name for p in f.parent.iterdir()] == ["a.json"]  # the old file stays, no temporary file is left


def test_manifest_read_write_and_policy(tmp_path) -> None:
    assert read_manifest(tmp_path) is None
    m = new_manifest(name="n", data_sha="d", rows=1, bars={"discovery": 1}, splits={}, policy={"fdr_q": 0.05}, profile=None, grammar=None, data_path=None)
    assert m["policy"]["fdr_q"] == 0.05 and m["policy"]["alpha"] == DEFAULT_POLICY["alpha"]
    with pytest.raises(ValueError, match="unknown policy keys"):
        new_manifest(name="n", data_sha="d", rows=1, bars={}, splits={}, policy={"oops": 1}, profile=None, grammar=None, data_path=None)
    write_manifest(tmp_path, m)
    assert read_manifest(tmp_path)["name"] == "n"
    (tmp_path / "manifest.json").write_text("{not json")
    with pytest.raises(ValueError, match="damaged"):
        read_manifest(tmp_path)
    (tmp_path / "manifest.json").write_text(json.dumps({"schema": "other/9"}))
    with pytest.raises(ValueError, match="unknown manifest schema"):
        read_manifest(tmp_path)


def test_lock_is_reentrant_exclusive_and_taken_over_when_stale(tmp_path) -> None:
    a = ProjectLock(tmp_path, timeout=0.2)
    with a.held():
        with a.held():  # re-entrant inside one process
            assert a.owner() == os.getpid()
        assert a.path.exists()
        with pytest.raises(ValueError, match="locked by process"):
            ProjectLock(tmp_path, timeout=0.2).acquire()  # another holder in the same process is still a holder
    assert not a.path.exists()
    a.path.write_text("999999 2020-01-01T00:00:00+00:00\n")  # a crashed run
    with ProjectLock(tmp_path, timeout=0.2).held():
        pass
    a.path.write_text("garbage")
    assert a.owner() is None
    with ProjectLock(tmp_path, timeout=0.2).held():
        pass


def test_lock_alive_check_covers_foreign_and_unknown_errors(tmp_path, monkeypatch) -> None:
    lock = ProjectLock(tmp_path)
    monkeypatch.setattr(os, "kill", lambda pid, sig: (_ for _ in ()).throw(PermissionError()))
    assert lock._alive(1) is True
    monkeypatch.setattr(os, "kill", lambda pid, sig: (_ for _ in ()).throw(OSError()))
    assert lock._alive(1) is False


# ---------------------------------------------------------------- grammar plugin
def test_grammar_grid_strategy_file_and_generator(tmp_path) -> None:
    g = tmp_path / "g.py"
    g.write_text(GRAMMAR)
    gr = load_grammar(g)
    assert len(gr) == 8 and gr.label == "ma" and gr.manifest_entry()["variants"] == 8 and {c.params["n"] for c in gr.candidates()} == {5, 10, 20, 40}
    (tmp_path / "s.py").write_text(SOURCE)
    (tmp_path / "g2.py").write_text("STRATEGY = 's.py'\ndef variants():\n    for n in (5, 10):\n        yield {'n': n}\n")
    assert [c.params for c in load_grammar(tmp_path / "g2.py").candidates()] == [{"n": 5}, {"n": 10}]
    d = demo_grammar()
    assert len(d) == len([1 for f in DEMO_GRID["fast"] for s in DEMO_GRID["slow"] if f < s]) and d.sha256


@pytest.mark.parametrize(("text", "msg"), [
    ("GRID = {'n': [1]}\n", "SOURCE"),
    ("SOURCE = 'x'\n", "GRID"),
    ("SOURCE = 'x'\nGRID = {'n': []}\n", "non-empty"),
    ("SOURCE = 'x'\ndef variants():\n    return []\n", "no variants"),
    ("STRATEGY = 'missing.py'\nGRID = {'n': [1]}\n", "not found"),
])
def test_grammar_errors(tmp_path, text, msg) -> None:
    f = tmp_path / "g.py"
    f.write_text(text)
    with pytest.raises((ValueError, FileNotFoundError), match=msg):
        load_grammar(f)
    with pytest.raises(FileNotFoundError):
        load_grammar(tmp_path / "none.py")


def test_grammar_refuses_too_many_variants(tmp_path) -> None:
    f = tmp_path / "g.py"
    f.write_text(f"SOURCE = 'x'\ndef variants():\n    for i in range({MAX_VARIANTS + 5}):\n        yield {{'i': i}}\n")
    with pytest.raises(ValueError, match="more than"):
        load_grammar(f)


# ---------------------------------------------------------------- pipeline, resume, status
def test_init_writes_manifest_and_uses_the_data_path_afterwards(tmp_path, csv, gfile) -> None:
    out = _init(tmp_path, csv, gfile, profile="trend_cta", policy={"fdr_q": 0.05})
    p = ResearchProject(tmp_path / "p")
    assert p.manifest["stage"] == "init" and p.profile == "trend_cta" and p.policy["fdr_q"] == 0.05 and out["grammar"]["variants"] == 8
    assert p.manifest["data"]["path"] == str(csv.resolve())
    with pytest.raises(ValueError, match="unknown profile"):
        run_action(tmp_path / "q", "init", data=csv, discovery_end=str(TS.iloc[500]), validation_end=str(TS.iloc[750]), profile="nope")
    p2 = ResearchProject.create(tmp_path / "np", DF, TS.iloc[500], TS.iloc[750])  # a DataFrame has no path: --data must then be given
    with pytest.raises(ValueError, match="give the data file"):
        p2.screen(None, [])


def test_screen_resumes_after_a_time_limit_and_reports_progress(tmp_path, csv, gfile) -> None:
    _init(tmp_path, csv, gfile)
    first = run_action(tmp_path / "p", "screen", chunk=3, max_seconds=0.0)  # stops before the first chunk
    assert first["done"] == 0 and first["total"] == 8 and not first["complete"]
    p = ResearchProject(tmp_path / "p")
    seen: list[dict] = []
    info = p.screen_grammar(None, load_grammar(gfile), chunk=3, on_progress=seen.append)
    assert info["complete"] and info["done"] == 8 and [s["done"] for s in seen] == [3, 6, 8] and seen[-1]["eta_seconds"] == 0.0
    again = run_action(tmp_path / "p", "screen")
    assert again["new"] == 0 and again["complete"]  # the same command after a finished run changes nothing


def test_a_changed_grammar_is_a_different_search(tmp_path, csv, gfile) -> None:
    _init(tmp_path, csv, gfile)
    gfile.write_text(GRAMMAR.replace("[5, 10, 20, 40]", "[5, 10, 20, 40, 80]"))
    with pytest.raises(ValueError, match="grammar file changed"):
        run_action(tmp_path / "p", "screen")


def test_screen_without_a_grammar_uses_a_strategy_file(tmp_path, csv) -> None:
    run_action(tmp_path / "p", "init", data=csv, discovery_end=str(TS.iloc[500]), validation_end=str(TS.iloc[750]))
    s = tmp_path / "s.py"
    s.write_text(SOURCE)
    assert run_action(tmp_path / "p", "screen", strategy=s, grid={"n": [5, 10]})["n_screened"] == 2
    with pytest.raises(ValueError, match="strategy or a grammar"):
        run_action(tmp_path / "p", "screen")


def test_grammar_given_at_screen_time_is_recorded(tmp_path, csv, gfile) -> None:
    run_action(tmp_path / "p", "init", data=csv, discovery_end=str(TS.iloc[500]), validation_end=str(TS.iloc[750]))
    run_action(tmp_path / "p", "screen", grammar=gfile)
    assert ResearchProject(tmp_path / "p").manifest["grammar"]["variants"] == 8


def test_status_through_the_stages(tmp_path, csv, gfile) -> None:
    _init(tmp_path, csv, gfile)
    st = run_action(tmp_path / "p", "status")
    assert st["stage"] == "init" and st["progress"]["done"] == 0 and "screen" in st["next"] and "project t" in st["text"]
    assert "promoted 0 in 0 batch" in st["text"]
    run_action(tmp_path / "p", "screen", chunk=2, max_seconds=0.0)
    run_action(tmp_path / "p", "screen")
    st = run_action(tmp_path / "p", "status")
    assert st["stage"] == "screening" and st["progress"]["fraction"] == 1.0 and "promote" in st["next"] and "100 %" in st["text"]
    run_action(tmp_path / "p", "promote", top=3, min_sharpe=-1e9)
    assert run_action(tmp_path / "p", "status")["stage"] == "promoted"
    run_action(tmp_path / "p", "validate")
    st = run_action(tmp_path / "p", "status")
    assert st["stage"] == "validated" and st["validated_batches"] == 1 and "no candidate is frozen" in st["next"] and st["chain_ok"] and st["running"] is False


def test_status_shows_a_running_lock_eta_and_a_broken_record(tmp_path, csv, gfile) -> None:
    _init(tmp_path, csv, gfile)
    p = ResearchProject(tmp_path / "p")
    p._save(progress={"phase": "screen", "done": 2, "total": 8, "rate_per_s": 0.5, "eta_seconds": None})
    with p.lock.held():
        st = project_status(ResearchProject(tmp_path / "p"))
    assert st["progress"]["eta_seconds"] == pytest.approx(16.0) and st["progress"]["done"] == 0  # recomputed from the record: nothing screened yet
    p.lock.path.write_text(f"{os.getpid()} now\n")
    assert project_status(ResearchProject(tmp_path / "p"))["running"] is True
    p.lock.path.unlink()
    gfile.write_text(GRAMMAR + "# edited\n")  # the grammar no longer matches the manifest: progress is taken from the manifest
    assert project_status(ResearchProject(tmp_path / "p"))["progress"]["done"] == 2
    gfile.unlink()
    assert project_status(ResearchProject(tmp_path / "p"))["progress"]["grammar_unreadable"] is True
    f = tmp_path / "p" / "research.jsonl"
    f.write_text(f.read_text().replace('"name": "t"', '"name": "x"', 1))
    with pytest.raises(ValueError, match="was changed"):
        ResearchProject(tmp_path / "p")


def test_a_half_written_last_line_is_dropped_on_open(tmp_path, csv, gfile) -> None:
    _init(tmp_path, csv, gfile)
    run_action(tmp_path / "p", "screen")
    f = tmp_path / "p" / "research.jsonl"
    before = len(f.read_text().splitlines())
    with f.open("a") as h:
        h.write('{"seq": 99, "kind": "screen", "cand')  # a power cut in the middle of a line
    p = ResearchProject(tmp_path / "p")
    assert len(f.read_text().splitlines()) == before and p.log.check()["ok"] and project_status(p)["healed"] is True
    assert run_action(tmp_path / "p", "screen")["complete"]


# ---------------------------------------------------------------- pre-registration traps
def test_promote_writes_the_list_and_its_hash_before_validation(tmp_path, csv, gfile) -> None:
    _init(tmp_path, csv, gfile)
    run_action(tmp_path / "p", "screen")
    out = run_action(tmp_path / "p", "promote", top=2, min_sharpe=-1e9)
    f = tmp_path / "p" / "batches" / "batch001.json"
    on_disk = json.loads(f.read_text())
    assert on_disk["list_sha256"] == out["list_sha256"] == list_sha(out["candidates"]) and [e["kind"] for e in ResearchProject(tmp_path / "p").log.entries()][-1] == "prereg"
    assert list_sha(["a", "b"]) == list_sha(["b", "a"])


@pytest.mark.parametrize("tamper", ["edit", "remove", "garbage"])
def test_changing_the_batch_after_pre_registration_is_refused(tmp_path, csv, gfile, tamper) -> None:
    _init(tmp_path, csv, gfile)
    run_action(tmp_path / "p", "screen")
    run_action(tmp_path / "p", "promote", top=2, min_sharpe=-1e9)
    f = tmp_path / "p" / "batches" / "batch001.json"
    if tamper == "edit":
        d = json.loads(f.read_text())
        d["candidates"] = d["candidates"][:1]
        f.write_text(json.dumps(d))
    elif tamper == "remove":
        f.unlink()
    else:
        f.write_text("{oops")
    with pytest.raises(ValueError, match="pre-registered list was changed or removed"):
        run_action(tmp_path / "p", "validate")
    assert [e["action"] for e in ResearchProject(tmp_path / "p")._entries("refused")] == ["validate"]  # the attempt is in the record


def test_a_candidate_file_changed_after_screening_is_refused(tmp_path, csv, gfile) -> None:
    _init(tmp_path, csv, gfile)
    run_action(tmp_path / "p", "screen")
    run_action(tmp_path / "p", "promote", top=1, min_sharpe=-1e9)
    cid = ResearchProject(tmp_path / "p")._entries("prereg")[0]["candidates"][0]
    f = tmp_path / "p" / "candidates" / f"{cid.replace(':', '_')}.json"
    d = json.loads(f.read_text())
    d["params"]["n"] = 7
    f.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="were changed after screening"):
        run_action(tmp_path / "p", "validate")


def test_reading_validation_again_is_refused_logged_and_flagged(tmp_path, csv, gfile) -> None:
    p = _through_validate(tmp_path, csv, gfile)
    for _ in range(2):
        with pytest.raises(ValueError, match="already validated"):
            p.validate(None, batch=1)
    with pytest.raises(ValueError, match="no pre-registered batch waits"):
        p.validate(None)
    with pytest.raises(ValueError, match="was not pre-registered"):
        p.validate(None, batch=9)
    st = run_action(tmp_path / "p", "status")
    ids = {w["id"] for w in st["warnings"]}
    assert "reread_validation" in ids and "repeated_refusals" in ids and st["refused"] == 4


def test_holdout_needs_confirmation_a_candidate_and_opens_once(tmp_path, csv, gfile) -> None:
    p = _through_validate(tmp_path, csv, gfile)
    cid = p._validated()[0]
    with pytest.raises(ValueError, match="cannot be undone"):
        run_action(tmp_path / "p", "holdout", candidate=cid)
    with pytest.raises(ValueError, match="needs candidate"):
        run_action(tmp_path / "p", "holdout", confirm=True)
    with pytest.raises(ValueError, match="gate is closed"):
        run_action(tmp_path / "p", "holdout", candidate=cid, confirm=True)
    first = run_action(tmp_path / "p", "holdout", candidate=cid, confirm=True, override=True)
    assert first["valid"] is True and first["opens"] == 1
    second = run_action(tmp_path / "p", "holdout", confirm=True)
    assert second["valid"] is False and "more than once" in second["reason"]
    st = run_action(tmp_path / "p", "status")
    assert st["frozen"] == cid and st["holdout_opens"] == 2 and {"gate_overridden", "holdout_spoiled"} <= {w["id"] for w in st["warnings"]}
    assert "holdout" in status_text(st) or "frozen" in status_text(st)


def test_refused_freeze_is_in_the_record(tmp_path, csv, gfile) -> None:
    p = _through_validate(tmp_path, csv, gfile)
    with pytest.raises(ValueError, match="was not validated"):
        p.freeze(None, "ast:nope")
    with pytest.raises(ValueError, match="nothing is frozen"):
        p.open_holdout(None)
    assert [e["action"] for e in p._entries("refused")] == ["freeze", "open_holdout"]


# ---------------------------------------------------------------- forward journal
def _frozen(tmp_path, csv, gfile):
    p = _through_validate(tmp_path, csv, gfile)
    run_action(tmp_path / "p", "holdout", candidate=p._validated()[0], confirm=True, override=True)
    return ResearchProject(tmp_path / "p")


def _longer(extra: int, tmp_path) -> pd.DataFrame:
    long = _df(N + extra)
    long.iloc[:N, 1:] = DF.iloc[:, 1:].to_numpy()  # the old history is unchanged
    f = tmp_path / "long.csv"
    long.to_csv(f, index=False)
    return long


def test_forward_journal_catches_up_is_idempotent_and_flags_late_bars(tmp_path, csv, gfile) -> None:
    p = _frozen(tmp_path, csv, gfile)
    j = ForwardJournal(p)
    with pytest.raises(ValueError, match="no start"):
        j.record(csv)
    assert j.status()["started"] is False
    start = j.freeze(csv)
    assert start["start"].startswith(str(TS.iloc[-1].date()))
    with pytest.raises(ValueError, match="already has a start"):
        j.freeze(csv)
    long = _longer(12, tmp_path)
    r = j.record(long, now=pd.Timestamp("2030-01-01"))
    assert r["new"] == 12 and r["late"] == 12
    assert j.record(long)["new"] == 0  # idempotent
    st = j.status()
    assert st["bars"] == 12 and st["chain_ok"] and st["late_bars"] == 12 and st["held_bars"] <= 12
    longer = _longer(15, tmp_path)
    assert j.record(longer, now=pd.Timestamp(longer["timestamp"].iloc[-1]))["new"] == 3  # resumes after a gap, on time
    assert ForwardJournal(ResearchProject(tmp_path / "p")).status()["late_bars"] == 12


def test_forward_journal_traps(tmp_path, csv, gfile) -> None:
    p = _frozen(tmp_path, csv, gfile)
    j = ForwardJournal(p)
    with pytest.raises(ValueError, match="nothing is frozen"):
        ForwardJournal(_through_validate(tmp_path / "other", csv, gfile)).freeze(csv)
    j.freeze(csv)
    rewritten = _longer(5, tmp_path)
    rewritten.loc[10, "close"] *= 1.5
    with pytest.raises(ValueError, match="history before the start was rewritten"):
        j.record(rewritten)
    with pytest.raises(ValueError, match="history before the start was rewritten"):
        j.record(DF.head(100))
    far = _longer(MAX_BARS_PER_RUN + 2, tmp_path)
    with pytest.raises(ValueError, match="bars are missing"):
        j.record(far)
    j.record(_longer(3, tmp_path))
    f = tmp_path / "p" / "forward.jsonl"
    f.write_text(f.read_text().replace('"return"', '"retorn"', 1))
    with pytest.raises(ValueError, match="forward journal was changed"):
        j.record(_longer(4, tmp_path))
    assert j.status()["chain_ok"] is False


def test_forward_rule_changed_after_the_start_is_refused(tmp_path, csv, gfile, monkeypatch) -> None:
    p = _frozen(tmp_path, csv, gfile)
    j = ForwardJournal(p)
    j.freeze(csv)
    monkeypatch.setattr("monte_neo.research.forward.frozen_source", lambda s, par: s + "\nX = 1\n")
    with pytest.raises(ValueError, match="frozen rule changed"):
        j.record(_longer(3, tmp_path))


def test_forward_cli_steps(tmp_path, csv, gfile, capsys) -> None:
    from monte_neo.cli.research_cmd import main

    _frozen(tmp_path, csv, gfile)
    base = ["--project", str(tmp_path / "p"), "--format", "json"]
    assert main(["forward", *base]) == 3  # no step
    capsys.readouterr()
    assert main(["forward", "status", *base]) == 0 and json.loads(capsys.readouterr().out)["started"] is False
    assert main(["forward", "freeze", *base, "--data", str(csv)]) == 0
    capsys.readouterr()
    _longer(4, tmp_path)
    assert main(["forward", "record", *base, "--data", str(tmp_path / "long.csv")]) == 0
    assert json.loads(capsys.readouterr().out)["new"] == 4


# ---------------------------------------------------------------- hand-off
def test_handoff_writes_dossier_and_hall_entry_for_the_frozen_champion(tmp_path, csv, gfile) -> None:
    p = _frozen(tmp_path, csv, gfile)
    with pytest.raises(ValueError, match="no certificate yet"):
        handoff(p, dossier_dir=tmp_path / "d")
    run_action(tmp_path / "p", "certify")
    with pytest.raises(ValueError, match="give dossier_dir and/or hall_dir"):
        handoff(p)
    with pytest.raises(ValueError, match="author, name and category"):
        handoff(p, hall_dir=tmp_path / "h")
    out = handoff(p, dossier_dir=tmp_path / "d", hall_dir=tmp_path / "h", author="A. Person", name="demo trend", category="trend", tier="C")
    assert (tmp_path / "d").is_dir() and out["hall"]["entry"] and (tmp_path / "h" / "entries").is_dir() and out["certificate_id"]
    via_service = run_action(tmp_path / "p", "handoff", dossier_dir=tmp_path / "d2")
    assert "dossier" in via_service


def test_handoff_needs_a_frozen_champion(tmp_path, csv, gfile) -> None:
    p = _through_validate(tmp_path, csv, gfile)
    with pytest.raises(ValueError, match="nothing is frozen"):
        handoff(p, dossier_dir=tmp_path / "d")
    assert p.certificate_of("ast:none") is None


# ---------------------------------------------------------------- small branches
def test_lock_of_a_live_foreign_process_and_status_age_helper() -> None:
    from monte_neo.research.status import _age

    assert ProjectLock(Path_(".")) ._alive(os.getppid()) is True
    assert _age(None) is None and _age("not a date") is None and _age("2020-01-01T00:00:00+00:00") > 0


def test_project_api_promote_certify_candidate_and_a_project_without_manifest(tmp_path, csv, gfile) -> None:
    _init(tmp_path, csv, gfile)
    p = ResearchProject(tmp_path / "p")
    p.screen_grammar(None, load_grammar(gfile))
    out = p.promote(top=2, min_sharpe=-1e9, rule="two best")
    assert out["batch"] == 1 and out["rule"] == "two best" and out["list_sha256"] == list_sha(out["candidates"]) and out["n_trials"] == 2
    with pytest.raises(ValueError, match="promote needs"):
        p.promote(top=0)
    assert p.promote(ids=[p.top_candidates(1, min_sharpe=-1e9)[0]])["n_trials"] == 3
    with pytest.raises(ValueError, match="was not validated"):
        p.certify_candidate(None, out["candidates"][0])
    (tmp_path / "p" / "manifest.json").unlink()
    bare = ResearchProject(tmp_path / "p")  # an old project without a manifest still works
    assert bare.manifest is None and bare.policy == DEFAULT_POLICY
    bare._save(stage="screening")


def test_the_hall_can_refuse_the_entry(tmp_path, csv, gfile) -> None:
    p = _frozen(tmp_path, csv, gfile)
    run_action(tmp_path / "p", "certify")
    with pytest.raises(ValueError, match="unknown category"):
        handoff(p, hall_dir=tmp_path / "h", author="A", name="n", category="nope")
