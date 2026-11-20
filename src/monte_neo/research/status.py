"""``research status``: where the project stands, how far a running step is, how long it still needs, and what to do next."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from monte_neo.research.grammar import load_grammar
from monte_neo.research.project import ResearchProject
from monte_neo.research.report import antipatterns

NEXT = {
    "init": "screen: `research screen --grammar grammar.py` runs every variant on the discovery part only",
    "screening": "promote: `research promote --top 5` pre-registers the batch to validate (the list is written before validation is read)",
    "promoted": "validate: `research validate` reads the validation part once for the pre-registered batch",
    "validated": "report: `research report`; if a candidate passes the gate, `research holdout --candidate ID --confirm` opens the holdout once",
    "frozen": "open the holdout: `research holdout --confirm` (one opening only)",
    "holdout_opened": "certify and hand over: `research certify`, then `research handoff`; record it forward with `research forward`",
    "reported": "forward: `research forward record` keeps a hash-chained forward journal of the frozen rule",
}


def _age(stamp: str | None) -> float | None:
    if not stamp:
        return None
    try:
        return (datetime.now(UTC) - datetime.fromisoformat(stamp)).total_seconds()
    except ValueError:
        return None


def _next(stage: str, project: ResearchProject) -> str:
    if stage in ("validated", "reported") and not project._entries("freeze"):
        return ("no candidate is frozen: read the next actions of `research report` (they add information, not variants); `research holdout --candidate ID --confirm` is only for a candidate "
                "whose validation gate is open")
    return NEXT.get(stage, "")


def project_status(project: ResearchProject) -> dict[str, Any]:
    """Stage, counts, progress with ETA, lock, chain integrity, warnings and the next step."""
    chain = project.log.check()
    man = project.manifest or {}
    stage = man.get("stage", "init")
    entries = project.log.entries()
    screened = project.screened()
    prog = dict(man.get("progress") or {})
    g = man.get("grammar")
    if g and g.get("path"):
        try:  # recompute from the record: the manifest may be older than the last chunk if the run was killed
            gr = load_grammar(g["path"])
            if gr.sha256 == g.get("sha256"):
                n_done = len([c for c in gr.candidates() if c.id in screened])
                prog.update({"phase": "screen", "done": n_done, "total": len(gr), "from_record": True})
        except (OSError, ValueError, ImportError):
            prog["grammar_unreadable"] = True
    owner = project.lock.owner()
    running = bool(owner is not None and owner != 0 and project.lock._alive(owner) and project.lock.path.exists())
    done: Any = prog.get("done")
    total: Any = prog.get("total")
    rate: Any = prog.get("rate_per_s")
    eta = (total - done) / rate if (rate and done is not None and total is not None and done < total) else prog.get("eta_seconds")
    if prog and done is not None and total:
        prog["fraction"] = done / total
        prog["eta_seconds"] = eta
    warns = antipatterns(project)
    last = entries[-1] if entries else {}
    return {"project": project.name, "stage": stage, "chain_ok": chain["ok"], "chain_entries": chain["entries"], "chain_problem": chain["problem"],
            "n_screened": len(screened), "n_trials": project.n_trials, "n_promoted": len(project.promoted()), "batches": len(project._entries("prereg")), "validated_batches": len(project._entries("validate")),
            "refused": len(project._entries("refused")), "frozen": next((e["candidate"] for e in entries if e.get("kind") == "freeze"), None),
            "holdout_opens": len(project._entries("holdout_open")), "progress": prog or None, "running": running, "lock_owner": owner if running else None,
            "last_activity": last.get("at"), "seconds_since_activity": _age(last.get("at")), "warnings": warns, "next": _next(stage, project), "healed": (project.path / "healed.log").exists()}


def status_text(st: dict[str, Any]) -> str:
    lines = [f"project {st['project']}: stage {st['stage']}, record {'intact' if st['chain_ok'] else 'BROKEN: ' + str(st['chain_problem'])} ({st['chain_entries']} entries)",
             f"screened {st['n_screened']}, promoted {st['n_promoted']} in {st['batches']} batch(es), validated {st['validated_batches']}, refused steps {st['refused']}"]
    p = st["progress"]
    if p and p.get("total"):
        eta = f", about {p['eta_seconds'] / 60:.1f} min left" if p.get("eta_seconds") else ""
        lines.append(f"progress: {p['done']}/{p['total']} ({100 * p['done'] / p['total']:.0f} %){eta}" + (" [a command is running]" if st["running"] else ""))
    if st["frozen"]:
        lines.append(f"frozen: {st['frozen']}; holdout opened {st['holdout_opens']} time(s)")
    lines += [f"! [{w['severity']}] {w['text']}" for w in st["warnings"]]
    lines.append("next: " + st["next"])
    return "\n".join(lines)


__all__ = ["NEXT", "project_status", "status_text"]
