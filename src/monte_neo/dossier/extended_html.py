"""HTML for the ``extended`` section of a dossier (no scripts, no network)."""

from __future__ import annotations

from typing import Any

from monte_neo.verify.report_html import _e

_TONE = {"pass": "good", "met": "good", "warn": "warn", "fail": "bad", "failed": "bad"}


def _pill(text: str) -> str:
    return f"<span class='pill {_TONE.get(text, 'mute')}'>{_e(text)}</span>"


def _rows(rows: list[dict[str, Any]]) -> str:
    body = "".join(f"<tr><td class='mono'>{_e(r['id'])}</td><td>{_pill(r['status'])}</td><td>{_e(r['summary'])}</td></tr>" for r in rows)
    return f"<table><tr><th>Check</th><th>Status</th><th>What it says</th></tr>{body}</table>"


def _levels(levels: list[dict[str, Any]]) -> str:
    out = []
    for x in levels:
        depth = "; ".join(f"{d['id']} {d['name']}: {d['state']} ({d['why']})" for d in x["depth"])
        out.append(f"<tr><td>{x['level']}</td><td>{_e(x['name'])}</td><td>{_pill(x['state'])} {_e(x['state'])}</td>"
                   f"<td class='mono'>{_e(', '.join(x['blocking']))}</td><td class='small'>{_e(depth)}</td></tr>")
    return f"<table><tr><th>ARL</th><th>Level</th><th>State</th><th>Blocking</th><th>Depth D1 to D4, with reasons</th></tr>{''.join(out)}</table>"


def _funnel(search: dict[str, Any]) -> str:
    f = search.get("funnel")
    stages = "".join(f"<tr><td>{_e(s['stage'])}</td><td>{s['count']}</td></tr>" for s in (f or {}).get("stages", []))
    cost = search.get("search_cost")
    verdicts = ", ".join(f"{k}: {v}" for k, v in search["verdicts"].items())
    return (f"<p>{_e(search['note'])}</p><p>Certificates: {search['certificates']} ({_e(verdicts)}) · largest declared n_trials: {search['n_trials_max']}</p>"
            + (f"<table><tr><th>Stage</th><th>Count</th></tr>{stages}</table>" if stages else "<p class='muted'>No search funnel provided.</p>")
            + (f"<p class='small'>Search cost: {_e(str(cost))}</p>" if cost else ""))


def render_extended(ext: dict[str, Any]) -> str:
    """The extended sections as HTML fragments to insert into the dossier page."""
    parts = [f"<h2>Search: funnel and cost</h2><div class='card'>{_funnel(ext['search'])}</div>"]
    for s in ext["strategies"]:
        arl = s["arl"]
        m = " · ".join(f"{k} {v:.4g}" if isinstance(v, float) else f"{k} {v}" for k, v in s["metrics"].items())
        periods = " · ".join(f"{p['period']} {p['return']:+.1%}" for p in s["periods"])
        parts.append(
            f"<h2>Strategy <span class='mono'>{_e(s['certificate_id'])}</span>: {_e(s['verdict'])}</h2><div class='card'>"
            f"<p><b>{_e(arl['headline'])}</b>{' · profile ' + _e(s['profile']) if s['profile'] else ''} · n_trials {_e(s['n_trials'])}</p>"
            f"<p class='small muted'>{_e(m)}</p>{_levels(s['levels'])}"
            f"<h3>Regimes</h3>{_rows(s['regimes'])}" + (f"<p class='small'>Periods: {_e(periods)}</p>" if periods else "")
            + f"<h3>Costs</h3>{_rows(s['costs'])}<h3>Capacity</h3>{_rows(s['capacity'])}</div>")
    pf, mon = ext.get("portfolio"), ext.get("monitoring")
    parts.append("<h2>Portfolio</h2><div class='card'>" + (f"<p>Verdict {_e(pf['verdict'])}</p>{_rows(pf['checks'])}" if pf else "<p class='muted'>Not provided: no portfolio report was given (monte-neo verify portfolio).</p>") + "</div>")
    parts.append("<h2>Monitoring</h2><div class='card'>" + (f"<p>Verdict {_e(mon['verdict'])}</p>{_rows(mon['checks'])}" if mon else "<p class='muted'>Not provided: no live-monitor report was given.</p>") + "</div>")
    return "".join(parts)


__all__ = ["render_extended"]
