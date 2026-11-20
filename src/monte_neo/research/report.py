"""The research report (``research-report/1``): funnel, search statistics, candidates, anti-patterns, diagnosis, hand-off, and its HTML.

Everything is read from the hash-chained record and the stored validation returns, so the report can be rebuilt at any time and
does not depend on the process that ran the search.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import numpy as np

from monte_neo import disclaimer
from monte_neo.research.diagnosis import diagnose
from monte_neo.research.funnel import funnel
from monte_neo.research.project import ResearchProject, _safe
from monte_neo.research.search_stats import effective_trials, power_row, search_statistics
from monte_neo.verify.report_html import CSP

REPORT_SCHEMA = "research-report/1"


def antipatterns(project: ResearchProject, stats: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Habits that fool the researcher, read from the record: each with severity, text and evidence."""
    es = project.log.entries()
    out: list[dict[str, Any]] = []
    refused = [e for e in es if e.get("kind") == "refused"]
    rereads = [e for e in refused if e.get("action") == "validate" and "already validated" in e.get("reason", "")]
    if rereads:
        out.append({"id": "reread_validation", "severity": "high", "text": f"validation was asked for again {len(rereads)} time(s) after it had been read: every look is a chance to adapt to it",
                    "evidence": [e["reason"] for e in rereads[:3]]})
    if len(refused) >= 3:
        out.append({"id": "repeated_refusals", "severity": "medium", "text": f"{len(refused)} steps were refused by the protocol: repeated attempts to get around it are themselves a sign of overfitting",
                    "evidence": [f"{e['action']}: {e['reason']}" for e in refused[:4]]})
    validated = [e for e in es if e.get("kind") == "validate"]
    if len(validated) >= 2:
        first, last = validated[0]["stats"]["n_candidates"], validated[-1]["stats"]["n_candidates"]
        sev = "high" if len(validated) >= 4 else "medium"
        out.append({"id": "n_grew_without_new_information", "severity": sev,
                    "text": f"{len(validated)} batches were validated on the same window: the number of tries grew from {first} to {last} and no new data came in, so each batch "
                            "after the first selects on a sample that has already been used",
                    "evidence": [f"batch {e['batch']}: {e['stats']['n_candidates']} candidates" for e in validated]})
    fz = next((e for e in es if e.get("kind") == "freeze"), None)
    if fz and fz.get("override"):
        out.append({"id": "gate_overridden", "severity": "high", "text": "the holdout was opened for a candidate whose validation gate was closed", "evidence": [fz["candidate"]]})
    opens = [e for e in es if e.get("kind") == "holdout_open"]
    if len(opens) > 1 or any(e.get("action") == "open_holdout" and "already opened" in e.get("reason", "") for e in refused):
        out.append({"id": "holdout_spoiled", "severity": "high", "text": "the sealed holdout was opened more than once: it no longer counts as evidence (D4 is 0 for every level)", "evidence": [f"{len(opens)} openings"]})
    if stats and stats.get("detectable", {}).get("min_detectable_sharpe_annual", 0) > 1.5:
        out.append({"id": "search_cannot_detect", "severity": "high", "text": "this search cannot detect a Sharpe an honest strategy earns; widening it makes that worse",
                    "evidence": [f"detectable annual Sharpe {stats['detectable']['min_detectable_sharpe_annual']:.2f} at {stats['detectable']['n_trials']} tries"]})
    return out


def _validation_matrix(project: ResearchProject) -> tuple[np.ndarray, list[str]]:
    ids = project._validated()
    mats = [np.load(project.path / "returns" / f"{_safe(c)}.npy") for c in ids]
    n = min(len(x) for x in mats)
    return np.vstack([x[-n:] for x in mats]), ids


def _screened_effective(project: ResearchProject, corr: float) -> dict[str, Any] | None:
    files = sorted((project.path / "disc_returns").glob("*.npy")) if (project.path / "disc_returns").is_dir() else []
    if len(files) < 2 or len(files) > 3000:
        return None
    mats = [np.load(f).astype(float) for f in files]
    n = min(len(x) for x in mats)
    eff = effective_trials(np.vstack([x[-n:] for x in mats]), corr)
    return {"screened": eff["n"], "n_clusters": eff["n_clusters"], "participation_ratio": eff["participation_ratio"], "n_eff": eff["n_eff"]}


def build_report(project: ResearchProject, *, certify: int = 0, data: Any = None, arl: bool = True) -> dict[str, Any]:
    """The ``research-report/1`` dict of a project.

    Args:
        project: The project.
        certify: Certify this many top validated candidates (by validation Sharpe) that have no certificate yet, to give each an ARL and depth. Needs the data.
        data: The data file (default: the one the project was created with).
        arl: Compute ARL and depth for candidates that have a certificate.
    """
    from monte_neo.readiness import readiness

    f = funnel(project)
    validated = project._validated()
    last = project._entries("validate")[-1]["stats"] if validated else None
    pol = project.policy
    search: dict[str, Any] = {"n_screened": f["n_screened"], "n_trials": project.n_trials, "screened_effective": _screened_effective(project, pol["cluster_corr"])}
    stats: dict[str, Any] | None = None
    cands: list[dict[str, Any]] = []
    if last:
        mat, ids = _validation_matrix(project)
        ppy = last["periods_per_year"]
        stats = search_statistics(mat, ids, ppy, fdr_q=pol["fdr_q"], alpha=pol["alpha"], power=pol["power"], cluster_corr=pol["cluster_corr"])
        stats["spa"], stats["search_cost"], stats["stepdown_significant"] = last["spa"], last["search_cost"], last["stepdown_significant"]
        search.update({"search_cost": last["search_cost"], "spa": last["spa"], "spa_passes": last["spa_passes"], "stepdown_significant": last["stepdown_significant"],
                       "fdr": {"q": pol["fdr_q"], "discoveries": stats["fdr_discoveries"], "pi0": stats["pi0"]}, "effective_trials": {k: v for k, v in stats["effective_trials"].items() if k != "clusters"},
                       "detectable": stats["detectable"], "detectable_effective": stats["detectable_effective"], "power": power_row(project.n_trials, len(mat[0]), ppy)})
        by_val = {c["id"]: c for c in last["candidates"]}
        by_fdr = {c["id"]: c for c in stats["candidates"]}
        order = sorted(ids, key=lambda c: -by_val[c]["sharpe_annual"])
        if certify:
            for cid in [c for c in order if project.certificate_of(c) is None][:certify]:
                project.certify_candidate(data, cid)
        screened = project.screened()
        for cid in order:
            cand = project._candidate(cid)
            v, q = by_val[cid], by_fdr[cid]
            cert = project.certificate_of(cid)
            ev = project.holdout_evidence() if any(e.get("candidate") == cid for e in project._entries("freeze")) else None
            row: dict[str, Any] = {"id": cid, "label": cand.label, "params": cand.params, "discovery_sharpe_annual": screened[cid].get("sharpe_annual"),
                                   "validation": {**v, "q_bh": q["q_bh"], "q_storey": q["q_storey"], "fdr_discovery": q["fdr_discovery"], "cluster": q["cluster"]},
                                   "gate_open": bool(v["stepdown_significant"] and v["beats_search_null"] and v["sharpe_annual"] > 0), "certificate_id": cert.get("certificate_id") if cert else None,
                                   "verdict": cert.get("verdict") if cert else None, "arl": None, "profile": None}
            if cert and arl:
                r = readiness(cert, n_trials=project.n_trials, holdout=ev)
                row["arl"] = {"level": r["level"], "depth": r["depth"], "headline": r["headline"]}
            if cert and project.profile:
                from monte_neo.profiles import profile_block

                row["profile"] = profile_block(project.profile, cert["checks"])
            row["_checks"] = {c["id"]: c for c in cert["checks"]} if cert else {}
            cands.append(row)
    fz = next((e for e in project._entries("freeze")), None)
    champion = None
    if fz:
        champion = next((c for c in cands if c["id"] == fz["candidate"]), {"id": fz["candidate"]})
        champion = {**{k: v for k, v in champion.items() if k != "_checks"}, "frozen": True, "holdout": {"valid": f["holdout_valid"], "opens": f["holdout_opens"]}, "final_arl": f["arl"]}
    elif cands and cands[0]["gate_open"]:
        champion = {**{k: v for k, v in cands[0].items() if k != "_checks"}, "frozen": False, "holdout": None, "final_arl": None}
    anti = antipatterns(project, stats)
    facts = {"n_trials": project.n_trials, "spa_passes": bool(last and last["spa_passes"]), "years": (last["n_bars"] / last["periods_per_year"]) if last else 0.0,
             "best_sharpe_annual": last["best_sharpe_annual"] if last else 0.0, "min_detectable_sharpe_annual": stats["detectable"]["min_detectable_sharpe_annual"] if stats else 0.0,
             "any_beats_null": bool(last and any(c["beats_search_null"] for c in last["candidates"])), "any_significant": bool(last and last["stepdown_significant"])}
    diag = diagnose(facts, [{"id": c["id"], "checks": c["_checks"]} for c in cands[:5]]) if last else {"groups": [], "next_actions": ["Screen candidates, promote a batch and validate it."], "passed": False}
    if last and diag["passed"] and champion and not champion["frozen"]:
        diag["next_actions"] = ["Freeze the champion and open the holdout once (`research holdout --candidate ID --confirm`), then record it forward (`research forward`)."]
    refusals = [{"action": e["action"], "reason": e["reason"], "at": e.get("at")} for e in project._entries("refused")]
    report = {"schema": REPORT_SCHEMA, "project": {"name": project.name, "stage": (project.manifest or {}).get("stage"), "data_sha256": project.data_id, "splits": project.splits.as_dict(),
                                                    "bars": (project.manifest or {}).get("bars"), "policy": pol, "profile": project.profile, "chain_entries": len(project.log.entries())},
              "funnel": f, "search": search, "candidates": [{k: v for k, v in c.items() if k != "_checks"} for c in cands], "champion": champion, "antipatterns": anti, "diagnosis": diag,
              "refusals": refusals, "disclaimer": disclaimer.SHORT}
    return report


def report_schema() -> dict[str, Any]:
    """JSON Schema of ``research-report/1`` (the stable fields)."""
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": REPORT_SCHEMA, "type": "object",
            "required": ["schema", "project", "funnel", "search", "candidates", "champion", "antipatterns", "diagnosis", "disclaimer"],
            "properties": {"schema": {"const": REPORT_SCHEMA}, "project": {"type": "object", "required": ["name", "stage", "data_sha256", "splits", "policy"]},
                           "funnel": {"type": "object", "required": ["stages", "n_trials", "n_screened"]}, "search": {"type": "object", "required": ["n_screened", "n_trials"]},
                           "candidates": {"type": "array", "items": {"type": "object", "required": ["id", "validation", "gate_open"]}},
                           "champion": {"type": ["object", "null"]}, "antipatterns": {"type": "array", "items": {"type": "object", "required": ["id", "severity", "text"]}},
                           "diagnosis": {"type": "object", "required": ["groups", "next_actions", "passed"]}, "refusals": {"type": "array"}, "disclaimer": {"type": "string"}}}


def render_text(rep: dict[str, Any]) -> str:
    """The report as plain text."""
    from monte_neo.research.funnel import funnel_text

    lines = [funnel_text(rep["funnel"]), ""]
    s = rep["search"]
    if "detectable" in s:
        d, e = s["detectable"], s["effective_trials"]
        lines.append(f"tries: {s['n_screened']} screened, {s['n_trials']} promoted (about {e['n_eff']} independent); detectable annual Sharpe {d['min_detectable_sharpe_annual']:.2f}")
        lines.append(f"FDR (q = {s['fdr']['q']}): {len(s['fdr']['discoveries'])} discoveries; {s['power']['summary']}")
    for c in rep["candidates"][:10]:
        v = c["validation"]
        arl = f", {c['arl']['headline']}" if c.get("arl") else ""
        lines.append(f"  {c['label'][:40]:<40} validation Sharpe {v['sharpe_annual']:+.2f}  q {v['q_bh']:.3f}  gate {'open' if c['gate_open'] else 'closed'}{arl}")
    for a in rep["antipatterns"]:
        lines.append(f"! [{a['severity']}] {a['text']}")
    for g in rep["diagnosis"]["groups"]:
        lines.append(f"- {g['title']}: " + "; ".join(g["evidence"][:2]))
    lines += [f"next: {a}" for a in rep["diagnosis"]["next_actions"][:4]]
    return "\n".join(lines)


def render_html(rep: dict[str, Any]) -> str:
    """A self-contained HTML page: the funnel as bars, the candidates, the anti-patterns and the diagnosis."""
    e = html.escape
    stages = rep["funnel"]["stages"]
    top = max([s["count"] for s in stages] + [1])
    bars = "".join(f'<div class="row"><span class="lab">{e(s["stage"])}</span><span class="bar" style="width:{max(2, int(100 * s["count"] / top))}%"></span><b>{s["count"]}</b></div>' for s in stages)
    rows = "".join(f'<tr><td>{e(c["label"])}</td><td>{c["validation"]["sharpe_annual"]:+.2f}</td><td>{c["validation"]["q_bh"]:.3f}</td><td>{"open" if c["gate_open"] else "closed"}</td>'
                   f'<td>{e(c["arl"]["headline"]) if c.get("arl") else "not certified"}</td></tr>' for c in rep["candidates"][:50])
    anti = "".join(f'<li class="{e(a["severity"])}">{e(a["text"])}</li>' for a in rep["antipatterns"]) or "<li>none</li>"
    diag = "".join(f'<li><b>{e(g["title"])}</b>: {e("; ".join(g["evidence"][:3]))}</li>' for g in rep["diagnosis"]["groups"]) or "<li>no cause found</li>"
    nxt = "".join(f"<li>{e(a)}</li>" for a in rep["diagnosis"]["next_actions"])
    champ = rep.get("champion")
    head = f'<p><b>Champion:</b> {e(str(champ.get("label", champ["id"])))} ({"frozen" if champ.get("frozen") else "not frozen"})</p>' if champ else "<p><b>No champion.</b></p>"
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="Content-Security-Policy" content="{CSP}"><title>Research report: {e(rep["project"]["name"])}</title>'
            '<style>body{font:15px system-ui,sans-serif;margin:2rem auto;max-width:60rem;padding:0 1rem;color:#222;background:#fff}'
            '@media(prefers-color-scheme:dark){body{color:#ddd;background:#16181c}}.row{display:flex;gap:.6rem;align-items:center;margin:.2rem 0}.lab{width:22rem;font-size:13px}'
            '.bar{height:.9rem;background:#3b82f6;border-radius:2px}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #8884;padding:.3rem .5rem;text-align:left}'
            'li.high{color:#c0392b}li.medium{color:#b9770e}</style></head><body>'
            f'<h1>Research report: {e(rep["project"]["name"])}</h1><p>stage {e(str(rep["project"]["stage"]))}, {rep["funnel"]["n_trials"]} promoted of {rep["funnel"]["n_screened"]} screened</p>{head}'
            f'<h2>Funnel</h2>{bars}<h2>Candidates</h2><table><tr><th>candidate</th><th>validation Sharpe</th><th>q (BH)</th><th>gate</th><th>ARL</th></tr>{rows}</table>'
            f'<h2>Anti-patterns</h2><ul>{anti}</ul><h2>Why it did not pass</h2><ul>{diag}</ul><h2>Next</h2><ul>{nxt}</ul>{disclaimer.html_footer()}</body></html>')


def write_report(project: ResearchProject, out: str | Path | None = None, **kw: Any) -> dict[str, Any]:
    """Build the report and write ``report.json`` and ``report.html`` (default: inside the project)."""
    from monte_neo.research.manifest import atomic_write

    rep = build_report(project, **kw)
    root = Path(out) if out else project.path
    atomic_write(root / "report.json", json.dumps(rep, indent=1, default=str) + "\n")
    atomic_write(root / "report.html", render_html(rep))
    project._save(stage="reported")
    return rep


__all__ = ["REPORT_SCHEMA", "antipatterns", "build_report", "render_html", "render_text", "report_schema", "write_report"]
