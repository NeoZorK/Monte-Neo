"""Honest search protocol: split, ledger, pre-registration, family statistics, one holdout, breadth."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from monte_neo.arl_depth import UNMET
from monte_neo.readiness import readiness
from monte_neo.research import (
    Candidate,
    ResearchProject,
    Splits,
    breadth_report,
    breadth_row,
    effective_breadth,
    family_stats,
    funnel,
    funnel_text,
    search_cost,
)
from monte_neo.research.candidate import frozen_source
from monte_neo.research.service import run_action, run_breadth

N, D_END, V_END = 3000, 1800, 2400  # bars; discovery < 1800 <= validation < 2400 <= holdout

SRC = '''
import numpy as np
def signal(df, k=1, side=1):
    """doc"""
    return np.full(len(df), side)
'''


def _df(drift: float = 0.0004, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(drift, 0.001, N)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame({"timestamp": pd.date_range("2024-01-01", periods=N, freq="min", tz="UTC"), "open": open_,
                         "high": np.maximum(open_, close) * 1.0002, "low": np.minimum(open_, close) * 0.9998, "close": close, "volume": 1.0})


DF = _df()
TS = DF["timestamp"]


def _project(tmp_path, df=DF):
    return ResearchProject.create(tmp_path / "p", df, TS.iloc[D_END], TS.iloc[V_END], name="t")


def _cands(*sides) -> list[Candidate]:
    return [Candidate(SRC, {"side": s}, f"side{s}") for s in sides]


# ---------------------------------------------------------------- splits
def test_split_counts_and_masks_are_disjoint() -> None:
    sp = Splits.build(DF, TS.iloc[D_END], TS.iloc[V_END])
    assert sp.bar_counts(DF) == {"discovery": D_END, "validation": V_END - D_END, "holdout": N - V_END}
    m = sp.masks(DF)
    assert (m["discovery"].astype(int) + m["validation"] + m["holdout"] == 1).all()
    assert len(sp.upto(DF, "discovery")) == D_END and len(sp.upto(DF, "validation")) == V_END
    with pytest.raises(ValueError, match="only discovery and validation"):
        sp.upto(DF, "holdout")


@pytest.mark.parametrize(("d", "v", "msg"), [(2000, 1000, "before"), (1800, 2990, "holdout part"), (1800, 1850, "validation part"), (30, 2000, "discovery part")])
def test_split_refuses_bad_cuts(d, v, msg) -> None:
    with pytest.raises(ValueError, match=msg):
        Splits.build(DF, TS.iloc[d], TS.iloc[v])


def test_split_by_bar_number_without_timestamps() -> None:
    plain = DF.drop(columns="timestamp")
    sp = Splits.build(plain, D_END, V_END)
    assert sp.bar_counts(plain)["discovery"] == D_END
    with pytest.raises(ValueError, match="integers"):
        Splits.build(plain, "2024-01-02", "2024-01-03")


def test_split_accepts_naive_cut_for_aware_data_and_exact_minimum() -> None:
    sp = Splits.build(DF, str(TS.iloc[D_END].tz_localize(None)), str(TS.iloc[V_END].tz_localize(None)))
    assert sp.bar_counts(DF)["discovery"] == D_END
    Splits.build(DF, TS.iloc[60], TS.iloc[160])  # exactly the minimum discovery and validation sizes


# ---------------------------------------------------------------- candidates
def test_candidate_id_ignores_docstrings_and_changes_with_code_or_params() -> None:
    a = Candidate(SRC, {"side": 1})
    assert a.id == Candidate(SRC.replace('"""doc"""', '"""other"""'), {"side": 1}).id
    assert a.id != Candidate(SRC, {"side": -1}).id
    assert a.id != Candidate(SRC.replace("np.full", "np.full_like(np.zeros(len(df)), 1) + 0 * np.full"), {"side": 1}).id
    assert Candidate(SRC, {"a": 1, "b": 2}).id == Candidate(SRC, {"b": 2, "a": 1}).id


def test_candidate_from_callable_and_file(tmp_path) -> None:
    def my_rule(df, side=1):
        return np.full(len(df), side)

    c = Candidate.from_callable(my_rule, {"side": 1})
    assert c.signal_fn()(DF).shape == (N,)
    f = tmp_path / "s.py"
    f.write_text(SRC)
    assert Candidate.from_file(f, {"side": 1}).signal_fn()(DF)[0] == 1
    with pytest.raises(FileNotFoundError):
        Candidate.from_file(tmp_path / "missing.py")
    with pytest.raises(ValueError, match="must define signal"):
        Candidate("x = 1").signal_fn()


def test_frozen_source_hash_covers_parameters() -> None:
    from monte_neo.verify.ledger import variant_id

    assert variant_id(frozen_source(SRC, {"side": 1})) != variant_id(frozen_source(SRC, {"side": -1}))


# ---------------------------------------------------------------- project: create / screen
def test_create_once_and_data_must_match(tmp_path) -> None:
    p = _project(tmp_path)
    assert p.splits.discovery_end.startswith("2024-01-02")
    with pytest.raises(ValueError, match="already holds"):
        _project(tmp_path)
    with pytest.raises(ValueError, match="not the data"):
        p.screen(_df(seed=9), _cands(1))
    with pytest.raises(ValueError, match="not a research project"):
        ResearchProject(tmp_path / "nothing")


def test_screen_sees_only_discovery_and_logs_every_variant(tmp_path) -> None:
    p = _project(tmp_path)
    broken = Candidate("def signal(df, **k):\n    raise RuntimeError('boom')\n", {}, "broken")
    rows = p.screen(DF, [*_cands(1, -1), broken])
    assert [r["bars"] for r in rows[:2]] == [D_END - 1] * 2  # the code was handed the discovery table only
    assert rows[2]["error"].startswith("RuntimeError") and rows[2]["sharpe_annual"] is None
    again = p.screen(DF, _cands(1))
    assert again[0]["repeat"] is True and len(p.screened()) == 3  # a repeat is not a new variant
    assert p.top_candidates(5) == [rows[0]["candidate"]]  # only the long one is above zero; the broken one never promotes
    assert p.top_candidates(0) == []


# ---------------------------------------------------------------- pre-registration
def test_preregister_rules(tmp_path) -> None:
    p = _project(tmp_path)
    c1, c2 = p.screen(DF, _cands(1, -1))
    with pytest.raises(ValueError, match="at least one"):
        p.preregister([], "r")
    with pytest.raises(ValueError, match="rule"):
        p.preregister([c1["candidate"]], "  ")
    with pytest.raises(ValueError, match="not screened"):
        p.preregister(["ast:0000"], "r")
    assert p.preregister([c1["candidate"]], "r") == 1
    with pytest.raises(ValueError, match="already promoted"):
        p.preregister([c1["candidate"]], "again")
    assert p.n_trials == 1 and p.preregister([c2["candidate"]], "second batch") == 2 and p.n_trials == 2


def test_validate_needs_a_batch_reads_once_and_orders_the_record(tmp_path) -> None:
    p = _project(tmp_path)
    ids = [r["candidate"] for r in p.screen(DF, _cands(1, -1))]
    with pytest.raises(ValueError, match="no pre-registered batch"):
        p.validate(DF)
    p.preregister(ids, "all")
    with pytest.raises(ValueError, match="not pre-registered"):
        p.validate(DF, batch=7)
    rep = p.validate(DF)
    kinds = [e["kind"] for e in p.log.entries()]
    assert kinds.index("prereg") < kinds.index("validation_read") < kinds.index("validate")
    assert rep["n_candidates"] == 2 and rep["n_trials_project"] == 2 and {r["id"] for r in rep["rows"]} == {"search_cost", "family_spa"}
    with pytest.raises(ValueError, match="already validated"):
        p.validate(DF, batch=1)


def test_second_batch_joins_the_family_and_raises_the_cost(tmp_path) -> None:
    p = _project(tmp_path)
    a, b, c = (r["candidate"] for r in p.screen(DF, _cands(1, -1, 2)))
    p.preregister([a], "first")
    one = p.validate(DF)
    p.preregister([b, c], "second")
    two = p.validate(DF)
    assert one["n_candidates"] == 1 and two["n_candidates"] == 3
    assert two["search_cost"]["expected_max_sharpe_annual"] > one["search_cost"]["expected_max_sharpe_annual"]


def test_changed_record_is_detected(tmp_path) -> None:
    p = _project(tmp_path)
    p.screen(DF, _cands(1))
    f = tmp_path / "p" / "research.jsonl"
    f.write_text(f.read_text().replace('"side": 1', '"side": 2'))
    with pytest.raises(ValueError, match="was changed"):
        ResearchProject(tmp_path / "p")


# ---------------------------------------------------------------- freeze, one holdout, funnel, ARL
def _validated(tmp_path):
    p = _project(tmp_path)
    ids = [r["candidate"] for r in p.screen(DF, _cands(1, -1))]
    p.preregister(ids, "all")
    rep = p.validate(DF)
    return p, ids, rep


def test_gate_open_for_a_real_edge_and_closed_for_a_loser(tmp_path) -> None:
    p, (win, lose), rep = _validated(tmp_path)
    by = {c["id"]: c for c in rep["candidates"]}
    assert by[win]["stepdown_significant"] and by[win]["beats_search_null"] and not by[lose]["stepdown_significant"]
    with pytest.raises(ValueError, match="gate is closed"):
        p.freeze(DF, lose)
    with pytest.raises(ValueError, match="was not validated"):
        p.freeze(DF, "ast:nope")
    with pytest.raises(ValueError, match="nothing is frozen"):
        p.open_holdout(DF)


def test_freeze_once_open_once_then_spoiled_for_good(tmp_path) -> None:
    p, (win, lose), _ = _validated(tmp_path)
    fr = p.freeze(DF, win)
    assert fr["gate_open"] is True and fr["override"] is False
    with pytest.raises(ValueError, match="already holds a freeze"):
        p.freeze(DF, lose, override=True)
    assert p.holdout_evidence()["valid"] is False  # frozen, not yet opened
    ev = p.open_holdout(DF)
    assert ev["valid"] is True and ev["opens"] == 1
    cert = p.certify(DF)
    assert cert["reproducibility"]["n_trials"] == 2
    assert {c["id"] for c in cert["checks"]} >= {"search_cost", "family_spa"}
    ok = funnel(p)
    assert ok["holdout_valid"] and ok["arl"]["headline"].startswith("ARL")
    again = p.open_holdout(DF)
    assert again["valid"] is False and "more than once" in again["reason"]
    spoiled = readiness(None, holdout=ResearchProject(tmp_path / "p").holdout_evidence())
    for lv in spoiled["levels"]:
        assert next(c for c in lv["depth_criteria"] if c["id"] == "D4")["state"] == UNMET
    f = funnel(ResearchProject(tmp_path / "p"))
    assert f["holdout_valid"] is False and f["holdout_opens"] == 2 and "NOT valid" in funnel_text(f)


def test_override_is_recorded_and_certify_needs_a_freeze(tmp_path) -> None:
    p, (win, lose), _ = _validated(tmp_path)
    with pytest.raises(ValueError, match="nothing is frozen"):
        p.certify(DF)
    fr = p.freeze(DF, lose, override=True)
    assert fr["gate_open"] is False and fr["override"] is True
    assert "overridden" in funnel_text(funnel(p))


def test_holdout_data_must_be_the_frozen_data(tmp_path) -> None:
    p, (win, _), _ = _validated(tmp_path)
    p.freeze(DF, win)
    with pytest.raises(ValueError, match="not the data"):
        p.open_holdout(_df(seed=11))


def test_funnel_counts_losers_too(tmp_path) -> None:
    p, _, _ = _validated(tmp_path)
    f = funnel(p)
    counts = {s["stage"]: s["count"] for s in f["stages"]}
    assert counts["variants tried on discovery"] == 2 and counts["promoted to validation"] == 2
    assert counts["positive validation Sharpe"] == 1 and counts["significant after Romano-Wolf"] == 1
    assert "ARL: not computed yet" in funnel_text(f)


# ---------------------------------------------------------------- family statistics
def test_search_cost_grows_with_trials_and_shrinks_with_sample() -> None:
    assert search_cost(1, 1000, 252)["expected_max_sharpe_annual"] == 0.0
    assert search_cost(100, 1000, 252)["expected_max_sharpe_annual"] > search_cost(10, 1000, 252)["expected_max_sharpe_annual"] > 0
    assert search_cost(100, 4000, 252)["expected_max_sharpe_annual"] < search_cost(100, 1000, 252)["expected_max_sharpe_annual"]
    assert search_cost(0, 1, 252)["n_trials"] == 1  # clamped


def test_family_stats_finds_a_planted_edge_and_not_noise() -> None:
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 0.01, (20, 1000))
    edge = rng.normal(0.003, 0.01, 1000)
    st = family_stats(np.vstack([noise, edge]), [f"n{i}" for i in range(20)] + ["edge"], 252.0)
    assert st["stepdown_significant"] == ["edge"] and st["spa_passes"] and st["best"] == "edge"
    st0 = family_stats(noise, [f"n{i}" for i in range(20)], 252.0)
    assert st0["stepdown_significant"] == [] and not st0["spa_passes"]
    assert not any(c["beats_search_null"] for c in st0["candidates"])


def test_family_stats_ignores_significant_losers_and_validates_shape() -> None:
    rng = np.random.default_rng(1)
    loser = rng.normal(-0.004, 0.01, 1000)
    st = family_stats(np.vstack([loser, rng.normal(0, 0.01, 1000)]), ["loser", "flat"], 252.0)
    assert "loser" not in st["stepdown_significant"]
    with pytest.raises(ValueError, match="one row per id"):
        family_stats(np.zeros((2, 100)), ["a"], 252.0)
    one = family_stats(rng.normal(0.004, 0.01, (1, 400)), ["solo"], 252.0)
    assert one["stepdown_significant"] == ["solo"] and one["spa"] == {}


# ---------------------------------------------------------------- breadth
def test_effective_breadth_bounds() -> None:
    rng = np.random.default_rng(2)
    base = rng.normal(size=(500, 1))
    same = np.hstack([base + 1e-6 * rng.normal(size=(500, 1)) for _ in range(10)])
    indep = rng.normal(size=(500, 10))
    assert effective_breadth(same)["n_eff"] < 1.2
    assert 7.0 < effective_breadth(indep)["n_eff"] <= 10.0
    assert effective_breadth(base)["n_eff"] == 1.0
    assert effective_breadth(np.hstack([indep, np.ones((500, 1))]))["n_names"] == 10  # a constant column is dropped
    with pytest.raises(ValueError, match="at least 30 dates"):
        effective_breadth(np.zeros((10, 3)))


def _panel(rows: int, names: int, common: float, ic: float, seed: int):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=rows, freq="D")
    sig = pd.DataFrame(rng.normal(size=(rows, names)), index=idx)
    market = rng.normal(size=(rows, 1))
    fwd = common * market + ic * sig.to_numpy() + rng.normal(size=(rows, names))
    return sig, pd.DataFrame(fwd, index=idx)


def test_breadth_counts_correlated_names_once() -> None:
    sig, fwd = _panel(400, 30, common=3.0, ic=0.15, seed=4)
    rep = breadth_report(sig, fwd)
    assert rep["n_eff"] < 0.5 * rep["n_names"] and rep["significance"] <= rep["z_naive"]
    assert rep["inflation_if_names_were_independent"] > 1.5 and rep["ir_annual_effective"] < rep["ir_annual_naive"]


def test_breadth_row_pass_warn_and_naive_only() -> None:
    sig, fwd = _panel(500, 30, common=0.0, ic=0.25, seed=5)
    assert breadth_row(breadth_report(sig, fwd))["status"] == "pass"
    nsig, nfwd = _panel(500, 30, common=0.0, ic=0.0, seed=6)
    assert breadth_row(breadth_report(nsig, nfwd))["status"] == "warn"
    fake = {"significance": 1.0, "z_naive": 3.5, "ic_mean": 0.02, "n_dates": 100, "n_names": 30, "n_eff": 3.0}
    row = breadth_row(fake)
    assert row["status"] == "warn" and "only if the names were independent" in row["summary"]


def test_breadth_needs_enough_dates() -> None:
    sig, fwd = _panel(20, 10, 0.0, 0.1, 7)
    with pytest.raises(ValueError, match="at least 30"):
        breadth_report(sig, fwd)


# ---------------------------------------------------------------- service, CLI, MCP
def test_service_end_to_end_and_irreversible_steps_need_confirm(tmp_path) -> None:
    csv = tmp_path / "d.csv"
    DF.to_csv(csv, index=False)
    strat = tmp_path / "s.py"
    strat.write_text(SRC)
    proj = tmp_path / "proj"
    run_action(proj, "init", data=csv, discovery_end=str(TS.iloc[D_END]), validation_end=str(TS.iloc[V_END]), name="svc")
    out = run_action(proj, "screen", data=csv, strategy=strat, grid={"side": [1, -1], "k": [1, 2]})
    assert out["n_screened"] == 4
    pre = run_action(proj, "preregister", top=2)
    assert pre["batch"] == 1 and "top 2" in pre["rule"]
    val = run_action(proj, "validate", data=csv)
    win = max(val["candidates"], key=lambda c: c["sharpe_annual"])["id"]
    with pytest.raises(ValueError, match="cannot be undone"):
        run_action(proj, "freeze", data=csv, candidate=win)
    run_action(proj, "freeze", data=csv, candidate=win, confirm=True)
    with pytest.raises(ValueError, match="cannot be undone"):
        run_action(proj, "open_holdout", data=csv)
    assert run_action(proj, "open_holdout", data=csv, confirm=True)["valid"] is True
    assert run_action(proj, "certify", data=csv)["certificate_id"]
    assert "holdout: opened 1" in run_action(proj, "funnel")["text"]
    with pytest.raises(ValueError, match="unknown action"):
        run_action(proj, "peek")
    with pytest.raises(ValueError, match="needs strategy"):
        run_action(proj, "screen", data=csv)
    with pytest.raises(ValueError, match="needs candidates"):
        run_action(proj, "preregister")
    none = run_action(proj, "promote", top=3, min_sharpe=1e9)
    assert none["candidates"] == [] and "normal outcome" in none["note"]


def test_cli_and_mcp_surfaces(tmp_path, capsys) -> None:
    from monte_neo.cli.research_cmd import main
    from monte_neo.mcp import tools

    csv = tmp_path / "d.csv"
    DF.to_csv(csv, index=False)
    base = ["--project", str(tmp_path / "pc")]
    assert main(["init", *base, "--data", str(csv), "--discovery-end", str(TS.iloc[D_END]), "--validation-end", str(TS.iloc[V_END]), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["splits"]["discovery_end"].startswith("2024-01-02")
    assert main(["init", *base, "--data", str(csv), "--discovery-end", "2024-01-02", "--validation-end", "2024-01-03"]) == 3  # a split is fixed once
    assert main(["freeze", *base, "--data", str(csv), "--candidate", "x"]) == 3  # no --confirm
    assert main(["funnel", *base]) == 0 and "Search funnel" in capsys.readouterr().out
    assert main(["breadth"]) == 3 and main(["--bogus"]) == 3
    assert tools.research_search in tools.TOOLS
    assert "error" not in tools.research_search(str(tmp_path / "pc"), "funnel")
    with pytest.raises(ValueError, match="cannot be undone"):
        tools.research_search(str(tmp_path / "pc"), "open_holdout", data_path=str(csv))


def test_breadth_cli_and_service(tmp_path, capsys) -> None:
    from monte_neo.cli.research_cmd import main

    sig, fwd = _panel(200, 12, 0.0, 0.2, 8)
    sig.to_csv(tmp_path / "s.csv")
    fwd.to_csv(tmp_path / "f.csv")
    out = run_breadth(tmp_path / "s.csv", tmp_path / "f.csv")
    assert out["check"]["id"] == "breadth_significance"
    assert main(["breadth", "--signal", str(tmp_path / "s.csv"), "--forward-returns", str(tmp_path / "f.csv")]) == 0
    assert "independent bets" in capsys.readouterr().out


def test_defensive_paths(tmp_path) -> None:
    p = _project(tmp_path)
    with pytest.raises(ValueError, match="nothing was validated"):
        p.family()
    ids = [r["candidate"] for r in p.screen(DF, _cands(1))]
    p.preregister(ids, "r")
    (tmp_path / "p" / "candidates" / f"{ids[0].replace(':', '_')}.json").unlink()
    with pytest.raises(ValueError, match="never screened"):
        p.validate(DF)
    with pytest.raises(ValueError, match="cannot read the source"):
        Candidate.from_callable(len)


def test_naive_data_with_an_aware_cut() -> None:
    naive = DF.assign(timestamp=DF["timestamp"].dt.tz_localize(None))
    sp = Splits.build(naive, TS.iloc[D_END], TS.iloc[V_END])  # an aware cut on naive data is converted
    assert sp.bar_counts(naive)["discovery"] == D_END


def test_text_output_of_a_step_and_a_cut_without_sealed_bars(tmp_path, capsys) -> None:
    from monte_neo.cli.research_cmd import main
    from monte_neo.verify.sealed_holdout import SealedHoldout

    csv = tmp_path / "d.csv"
    DF.to_csv(csv, index=False)
    args = ["init", "--project", str(tmp_path / "pt"), "--data", str(csv), "--discovery-end", str(TS.iloc[D_END]), "--validation-end", str(TS.iloc[V_END])]
    assert main(args) == 0 and '"splits"' in capsys.readouterr().out
    h = SealedHoldout(tmp_path / "h.jsonl")
    with pytest.raises(ValueError, match="no sealed bars"):
        h.freeze(DF, SRC, cut=TS.iloc[-1] + pd.Timedelta(days=1))
    assert h.freeze(DF, SRC, cut=TS.iloc[V_END])["cut"].startswith("2024-01-02")


def _returns_dir(tmp_path, n=400, edge=True):
    rng = np.random.default_rng(5)
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    d = tmp_path / "cands"
    d.mkdir()
    for i in range(6):
        pd.DataFrame({"date": idx, "return": rng.normal(0.0035 if (edge and i == 0) else 0.0, 0.01, n)}).to_csv(d / f"c{i}.csv", index=False)
    return d


def test_family_on_a_folder_a_wide_table_and_errors(tmp_path, capsys) -> None:
    from monte_neo.cli.research_cmd import main
    from monte_neo.research.service import run_family

    d = _returns_dir(tmp_path)
    out = run_family(d)
    assert out["stepdown_significant"] == ["c0"] and out["spa_passes"] and {r["id"] for r in out["rows"]} == {"search_cost", "family_spa"}
    wide = pd.concat({f.stem: pd.read_csv(f).set_index("date")["return"] for f in sorted(d.glob("*.csv"))}, axis=1)
    wide.reset_index().to_csv(tmp_path / "w.csv", index=False)
    assert run_family(tmp_path / "w.csv", periods_per_year=365)["best"] == "c0"
    flat = run_family(_returns_dir(tmp_path / "x" if (tmp_path / "x").mkdir() is None else tmp_path, edge=False))
    assert flat["stepdown_significant"] == []
    assert main(["family", "--returns", str(d)]) == 0 and "SPA p" in capsys.readouterr().out
    assert main(["family"]) == 3
    one = tmp_path / "one"
    one.mkdir()
    pd.read_csv(d / "c0.csv").to_csv(one / "a.csv", index=False)
    with pytest.raises(ValueError, match="at least two"):
        run_family(one)
    short = tmp_path / "short"
    short.mkdir()
    for n in ("a", "b"):
        pd.read_csv(d / "c0.csv").head(50).to_csv(short / f"{n}.csv", index=False)
    with pytest.raises(ValueError, match="at least 100"):
        run_family(short)
    bad = tmp_path / "bad"
    bad.mkdir()
    pd.DataFrame({"x": [1, 2]}).to_csv(bad / "a.csv", index=False)
    with pytest.raises(ValueError, match="needs a date column"):
        run_family(bad)


def test_freeze_needs_a_profitable_walk_forward_of_the_parameter_family(tmp_path, monkeypatch) -> None:
    p = _project(tmp_path)
    fam = [Candidate(SRC, {"side": 1, "k": k}, f"k{k}") for k in (1, 2, 3)]
    ids = [r["candidate"] for r in p.screen(DF, fam)]
    wf = p._family_walk_forward(p._candidate(ids[0]))
    assert wf is not None and wf["folds"] == 4 and wf["oos_sharpe"] > 0  # the same real edge in every variant: re-choosing works
    p.preregister(ids[:1], "best")
    p.validate(DF)
    monkeypatch.setattr(p, "_family_walk_forward", lambda c: {"oos_sharpe": -0.01, "folds": 4})
    with pytest.raises(ValueError, match="walk-forward of its parameter family"):
        p.freeze(DF, ids[0])
    fr = p.freeze(DF, ids[0], override=True)  # written down: the override is visible in the record
    assert fr["gate_open"] is False and fr["override"] is True and fr["walk_forward"]["oos_sharpe"] < 0


def test_a_family_too_small_for_walk_forward_relies_on_validation(tmp_path) -> None:
    p, (win, _lose), _ = _validated(tmp_path)
    assert p._family_walk_forward(p._candidate(win)) is None  # side 1 and side -1 are one variant each of the family; 2 < 3
    assert p.freeze(DF, win)["walk_forward"] is None
