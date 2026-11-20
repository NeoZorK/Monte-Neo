"""One entry point for the CLI, the MCP tool and scripts: ``run_action(project, action, ...)`` returns plain JSON data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from monte_neo.research.breadth import breadth_report, breadth_row
from monte_neo.research.candidate import Candidate
from monte_neo.research.funnel import funnel, funnel_text
from monte_neo.research.project import ResearchProject, list_sha

ACTIONS = ("init", "screen", "promote", "preregister", "validate", "freeze", "holdout", "open_holdout", "certify", "report", "status", "forward", "handoff", "funnel", "family")
IRREVERSIBLE = ("freeze", "holdout", "open_holdout")
FORWARD_STEPS = ("freeze", "record", "status")


def _plain(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))


def _need(value: Any, name: str, action: str) -> Any:
    if value is None:
        raise ValueError(f"{action} needs {name}")
    return value


def _dry_run(root: Path, name: str, profile: str | None) -> dict[str, Any]:
    """The whole pipeline on built-in synthetic data in ``root``: screen, promote, validate and report. Nothing real is found, by design."""
    import numpy as np

    from monte_neo.research.grammar import DEMO_GRID, DEMO_SOURCE
    from monte_neo.research.report import render_text, write_report

    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(11)
    n = 2500  # about ten years of daily bars of a driftless random walk
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    df = pd.DataFrame({"timestamp": pd.bdate_range("2015-01-01", periods=n, tz="UTC"), "open": open_, "high": np.maximum(open_, close) * 1.002, "low": np.minimum(open_, close) * 0.998,
                       "close": close, "volume": 1000.0})
    (root / "demo_data.csv").write_text(df.to_csv(index=False), encoding="utf-8")
    (root / "grammar.py").write_text(f"SOURCE = {DEMO_SOURCE!r}\nGRID = {DEMO_GRID!r}\nLABEL = 'demo-trend'\n", encoding="utf-8")
    ts = df["timestamp"]
    out = run_action(root, "init", data=root / "demo_data.csv", discovery_end=str(ts.iloc[1500]), validation_end=str(ts.iloc[2125]), name=name, grammar=root / "grammar.py", profile=profile)
    steps = [out]
    steps.append(run_action(root, "screen"))
    steps.append(run_action(root, "promote", top=3, min_sharpe=-1e9, rule="top 3 by discovery Sharpe (dry run: the sign is ignored on purpose)"))
    steps.append(run_action(root, "validate"))
    rep = write_report(ResearchProject(root))
    return {"action": "init", "dry_run": True, "project": str(root), "steps": [x["action"] for x in steps], "report": str(root / "report.html"), "text": render_text(rep),
            "note": "synthetic random-walk data: a correct run finds no candidate that passes the gate"}


def run_action(project: str | Path, action: str, *, data: str | Path | None = None, discovery_end: str | None = None, validation_end: str | None = None,
               name: str = "research", strategy: str | Path | None = None, grid: dict[str, list[Any]] | None = None, params: dict[str, Any] | None = None,
               top: int | None = None, min_sharpe: float = 0.0, candidates: list[str] | None = None, rule: str | None = None, batch: int | None = None,
               candidate: str | None = None, override: bool = False, confirm: bool = False, returns: str | Path | None = None,
               periods_per_year: float | None = None, grammar: str | Path | None = None, profile: str | None = None, policy: dict[str, Any] | None = None,
               chunk: int = 25, max_seconds: float | None = None, dry_run: bool = False, certify_top: int = 0, out: str | Path | None = None, step: str | None = None,
               dossier_dir: str | Path | None = None, hall_dir: str | Path | None = None, author: str | None = None, category: str | None = None,
               tier: str = "C") -> dict[str, Any]:
    """Run one step of the honest search protocol.

    Steps: init, screen, promote, validate, holdout, report, status, forward (``step`` freeze, record or status), handoff; ``funnel`` and ``family`` read only.

    Raises:
        ValueError: Unknown action, a missing argument, or a protocol rule that refuses the step.
    """
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}; one of {', '.join(ACTIONS)}")
    if action in IRREVERSIBLE and not confirm:
        raise ValueError(f"{action} cannot be undone (one frozen candidate, one opening of the holdout); repeat with confirm=True")
    if action == "family":  # needs no project: candidate returns that were tried elsewhere
        return {"action": action, **run_family(_need(returns, "returns", action), periods_per_year=periods_per_year)}
    if action == "init":
        if dry_run:
            return _plain(_dry_run(Path(project), name, profile))
        from monte_neo.research.grammar import load_grammar

        g = load_grammar(grammar) if grammar else None
        p = ResearchProject.create(project, _need(data, "data", action), _need(discovery_end, "discovery_end", action), _need(validation_end, "validation_end", action), name=name,
                                   policy=policy, profile=profile, grammar=g.manifest_entry() if g else None)
        return _plain({"action": action, "project": str(p.path), "splits": p.splits.as_dict(), "bars": p._entries("init")[0]["bars"], "grammar": g.manifest_entry() if g else None,
                       "policy": p.policy, "next": "screen: `research screen" + (" --grammar GRAMMAR`" if not g else "`")})
    p = ResearchProject(project)
    if action == "status":
        from monte_neo.research.status import project_status, status_text

        st = project_status(p)
        return _plain({"action": action, **st, "text": status_text(st)})
    if action == "screen":
        gpath = grammar or ((p.manifest or {}).get("grammar") or {}).get("path")
        if gpath and strategy is None:
            from monte_neo.research.grammar import load_grammar

            g = load_grammar(gpath)
            known = ((p.manifest or {}).get("grammar") or {})
            if known.get("sha256") and known["sha256"] != g.sha256:
                raise ValueError("the grammar file changed since init: a different grammar is a different search; start a new project")
            if not known and p.manifest is not None:
                p._save(grammar=g.manifest_entry())
            info = p.screen_grammar(data, g, chunk=chunk, max_seconds=max_seconds)
            return _plain({"action": action, **info, "n_screened": len(p.screened())})
        from monte_neo.verify.grid import expand_grid

        path = _need(strategy, "strategy or a grammar", action)
        combos = expand_grid(grid) if grid else [dict(params or {})]
        rows = p.screen(data, [Candidate.from_file(path, c, label=f"{Path(path).stem} {json.dumps(c, sort_keys=True)}") for c in combos])
        return _plain({"action": action, "screened": rows, "n_screened": len(p.screened())})
    if action in ("promote", "preregister"):
        ids = candidates or (p.top_candidates(int(top), min_sharpe=min_sharpe) if top else None)
        if not ids and top and not candidates:
            return _plain({"action": action, "batch": None, "candidates": [], "n_trials": p.n_trials,
                           "note": f"no candidate above min_sharpe {min_sharpe:g}: nothing promoted (a normal outcome, not an error)"})
        if not ids:
            raise ValueError(f"{action} needs candidates=[...] or top=K (with at least one candidate above min_sharpe)")
        text = rule or f"top {len(ids)} by discovery Sharpe above {min_sharpe:g}"
        batch_no = p.preregister(ids, text)
        return _plain({"action": action, "batch": batch_no, "candidates": ids, "rule": text, "n_trials": p.n_trials, "list_sha256": list_sha(ids)})
    if action == "validate":
        return _plain({"action": action, **p.validate(data, batch=batch)})
    if action == "freeze":
        return _plain({"action": action, **p.freeze(data, _need(candidate, "candidate", action), override=override)})
    if action == "holdout":
        if not p._entries("freeze"):
            p.freeze(data, _need(candidate, "candidate", action), override=override)
        ev = p.open_holdout(data)
        return _plain({"action": action, "valid": ev["valid"], "opens": ev["opens"], "certificate_id": ev.get("certificate_id"), "reason": ev.get("reason")})
    if action == "open_holdout":
        return _plain({"action": action, **p.open_holdout(data)})
    if action == "certify":
        rep = p.certify(data)
        return _plain({"action": action, "verdict": rep.get("verdict"), "certificate_id": rep.get("certificate_id"), "certificate": str(p.path / "certificate.json")})
    if action == "report":
        from monte_neo.research.report import render_text, write_report

        rep = write_report(p, out=out, certify=certify_top, data=data)
        return _plain({"action": action, "text": render_text(rep), "report": str(Path(out) if out else p.path), **rep})
    if action == "forward":
        from monte_neo.research.forward import ForwardJournal

        if step not in FORWARD_STEPS:
            raise ValueError(f"forward needs a step: {', '.join(FORWARD_STEPS)}")
        j = ForwardJournal(p)
        if step == "status":
            return _plain({"action": action, "step": step, **j.status()})
        d = _need(data if data is not None else ((p.manifest or {}).get("data") or {}).get("path"), "data (the current table, longer than the one of the project)", action)
        if step == "freeze":
            return _plain({"action": action, "step": step, **j.freeze(d)})
        return _plain({"action": action, "step": step, **j.record(d)})
    if action == "handoff":
        from monte_neo.research.handoff import handoff

        return _plain({"action": action, **handoff(p, dossier_dir=dossier_dir, hall_dir=hall_dir, author=author, name=name if name != "research" else None, category=category, tier=tier)})
    f = funnel(p)
    return _plain({"action": action, **f, "text": funnel_text(f)})


def run_breadth(signal_path: str | Path, returns_path: str | Path, *, periods_per_year: float = 252.0) -> dict[str, Any]:
    """Breadth-aware significance from two wide tables (first column the date, one column per name): signal and forward return."""
    def read(path: str | Path) -> pd.DataFrame:
        p = Path(path)
        df = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p, index_col=0)
        return df

    rep = breadth_report(read(signal_path), read(returns_path), periods_per_year=periods_per_year)
    return _plain({"report": rep, "check": breadth_row(rep)})


def run_family(returns: str | Path, *, periods_per_year: float | None = None, alpha: float = 0.05) -> dict[str, Any]:
    """Family-wise test of candidate return series that were not run through a project: White Reality Check, Hansen SPA and the
    Romano-Wolf stepdown for the null of zero return, plus the Sharpe luck delivers for that many candidates.

    ``returns`` is a folder of files (``.csv`` or ``.parquet``, columns date and return, one candidate per file) or one wide table
    (date and one column per candidate). Series are aligned on their dates; only dates present in every series are used.

    Raises:
        ValueError: Fewer than two candidates, fewer than 100 common dates, or unreadable files.
    """
    from monte_neo.research.family import family_rows, family_stats
    from monte_neo.verify.stats import infer_periods_per_year

    def read(p: Path) -> pd.DataFrame:
        return pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)

    path = Path(returns)
    if path.is_dir():
        files = sorted(f for f in path.iterdir() if f.suffix in (".csv", ".parquet"))
        cols = {}
        for f in files:
            d = read(f)
            d.columns = [str(c).strip().lower() for c in d.columns]
            if "return" not in d.columns or d.columns[0] == "return":
                raise ValueError(f"{f.name}: needs a date column and a return column")
            cols[f.stem] = pd.Series(pd.to_numeric(d["return"], errors="coerce").to_numpy(), index=pd.to_datetime(d[d.columns[0]]))
        wide = pd.DataFrame(cols)
    else:
        d = read(path)
        wide = d.set_index(pd.to_datetime(d[d.columns[0]])).drop(columns=d.columns[0]).apply(pd.to_numeric, errors="coerce")
    wide = wide.dropna()
    if wide.shape[1] < 2:
        raise ValueError("a family needs at least two candidates")
    if len(wide) < 100:
        raise ValueError(f"only {len(wide)} common dates; at least 100 are needed")
    ppy = periods_per_year or float(infer_periods_per_year(pd.Series(wide.index)))
    stats = family_stats(wide.to_numpy().T, [str(c) for c in wide.columns], ppy, alpha=alpha)
    return _plain({**stats, "rows": family_rows(stats)})


__all__ = ["ACTIONS", "IRREVERSIBLE", "run_action", "run_breadth", "run_family"]
