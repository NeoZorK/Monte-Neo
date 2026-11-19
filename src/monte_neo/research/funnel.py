"""The search funnel: how many variants were tried, how many went on, how many survived each gate, and the final ARL."""

from __future__ import annotations

import json
from typing import Any

from monte_neo.verify.chainlog import ChainLog

SCHEMA = "research-funnel/1"


def funnel(project: Any) -> dict[str, Any]:
    """Counts per stage from the project record (losers and winners alike), plus the ARL when a certificate exists."""
    log: ChainLog = project.log
    es = log.entries()
    screen = {}
    for e in es:
        if e.get("kind") == "screen":
            screen.setdefault(e["candidate"], e)
    batches = []
    last_stats = None
    for e in es:
        if e.get("kind") == "prereg":
            batches.append({"batch": e["batch"], "rule": e["rule"], "promoted": len(e["candidates"]), "validated": False})
        elif e.get("kind") == "validate":
            batches[e["batch"] - 1]["validated"] = True
            last_stats = e["stats"]
    tried = len(screen)
    errors = len([e for e in screen.values() if e.get("error")])
    positive = len([e for e in screen.values() if (e.get("sharpe_annual") or 0.0) > 0])
    promoted = project.promoted()
    stages = [("variants tried on discovery", tried), ("ran without error", tried - errors), ("positive discovery Sharpe", positive), ("promoted to validation", len(promoted))]
    if last_stats:
        cands = last_stats["candidates"]
        stages += [("validated", len(cands)), ("positive validation Sharpe", len([c for c in cands if c["sharpe_annual"] > 0])),
                   ("beat the Sharpe luck delivers for this search", len([c for c in cands if c["beats_search_null"]])),
                   ("significant after Romano-Wolf", len([c for c in cands if c["stepdown_significant"]])),
                   ("family SPA passes (all candidates)", 1 if last_stats["spa_passes"] else 0)]
    freeze = next((e for e in es if e.get("kind") == "freeze"), None)
    opens = [e for e in es if e.get("kind") == "holdout_open"]
    ev = project.holdout_evidence() if freeze else None
    if freeze:
        stages.append(("frozen for the holdout", 1))
        stages.append(("holdout opened once and valid", 1 if ev and ev["valid"] else 0))
    out: dict[str, Any] = {"schema": SCHEMA, "project": project.name, "n_trials": project.n_trials, "n_screened": tried, "batches": batches,
                           "stages": [{"stage": s, "count": c} for s, c in stages], "frozen": freeze["candidate"] if freeze else None,
                           "override": bool(freeze and freeze.get("override")), "holdout_opens": len(opens), "holdout_valid": bool(ev and ev["valid"]),
                           "search_cost": last_stats["search_cost"] if last_stats else None,
                           "spa": last_stats["spa"] if last_stats else None, "arl": None}
    cert = project.path / "certificate.json"
    if freeze and cert.is_file():
        from monte_neo.readiness import readiness

        rep = readiness(json.loads(cert.read_text(encoding="utf-8")), holdout=ev, n_trials=project.n_trials)
        out["arl"] = {"level": rep["level"], "depth": rep["depth"], "headline": rep["headline"]}
    return out


def funnel_text(f: dict[str, Any]) -> str:
    """The funnel as plain text, for a report you can publish."""
    lines = [f"Search funnel of {f['project']} (n_trials = {f['n_trials']}, every promoted candidate of every batch)", ""]
    width = max(len(s["stage"]) for s in f["stages"])
    lines += [f"  {s['stage']:<{width}}  {s['count']:>5}" for s in f["stages"]]
    lines.append("")
    lines += [f"batch {b['batch']}: {b['promoted']} promoted, {'validated' if b['validated'] else 'waiting'}; rule: {b['rule']}" for b in f["batches"]]
    c = f["search_cost"]
    if c:
        lines.append(f"search cost: luck alone gives a best Sharpe of {c['expected_max_sharpe_annual']:.2f} for {c['n_trials']} candidates on {c['n_obs']} bars")
    if f["spa"]:
        lines.append(f"SPA p = {f['spa']['p_spa']:.3f}, Reality Check p = {f['spa']['p_reality_check']:.3f}")
    if f["frozen"]:
        lines.append(f"frozen: {f['frozen']}" + (" (validation gate was overridden)" if f["override"] else ""))
        lines.append(f"holdout: opened {f['holdout_opens']} time(s), {'valid' if f['holdout_valid'] else 'NOT valid: D4 is 0 for every level'}")
    lines.append(f["arl"]["headline"] if f["arl"] else "ARL: not computed yet (certify after the freeze)")
    return "\n".join(lines)


__all__ = ["SCHEMA", "funnel", "funnel_text"]
