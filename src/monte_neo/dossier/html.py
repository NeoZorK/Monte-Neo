"""The dossier as one self-contained HTML page (no scripts, no network), printable to PDF from a browser."""

from __future__ import annotations

from typing import Any

from monte_neo import disclaimer
from monte_neo.verify.report_html import _CSS, _VERDICT_TONE, _checks_table, _e

_TONE = {"covered": "good", "partial": "warn", "not covered": "mute", "pass": "good", "warn": "warn", "fail": "bad", "—": "mute"}
_NEEDS_PERSON = " <span class='muted small'>needs a person</span>"
_EXTRA_CSS = ".sign td{height:38px}.small{font-size:13px}@media print{h2{break-after:avoid}.card{break-inside:avoid}}"


def _pill(text: str) -> str:
    return f"<span class='pill {_TONE.get(text, 'mute')}'>{_e(text)}</span>"


def _framework(fw: dict[str, Any]) -> str:
    rows = "".join(
        f"<tr><td><b>{_e(c['clause'])}</b><br><span class='muted small'>{_e(c['asks'])}</span></td>"
        f"<td>{_pill(c['coverage'])}{_NEEDS_PERSON if c['human_judgement'] else ''}</td>"
        f"<td>{_pill(c['result'])}</td><td class='mono'>{_e(', '.join(c['evidence']))}</td></tr>"
        for c in fw["clauses"]
    )
    return (f"<p class='muted'>{_e(fw['title'])}. Coverage means evidence in this dossier, not compliance: clauses marked "
            "&ldquo;needs a person&rdquo; require a judgement the verifier cannot make.</p>"
            f"<table><tr><th>Clause</th><th>Coverage</th><th>Result</th><th>Evidence</th></tr>{rows}</table>")


def _readiness(r: dict[str, Any] | None) -> str:
    if not r:
        return ""
    rows = "".join(
        f"<tr><td>{x['level']}</td><td>{_e(x['name'])}</td><td>{_pill({'met': 'pass', 'failed': 'fail'}.get(x['state'], '—'))} "
        f"{_e(x['state'])}</td><td class='mono'>{_e(', '.join(x['blocking']))}</td></tr>"
        for x in r["levels"]
    )
    return (f"<p><b>{_e(r['summary'])}</b></p><p class='muted small'>Rates the evidence, not the investment. "
            f"Next: {_e(r.get('next_step') or '—')}</p><table><tr><th>ARL</th><th>Level</th><th>State</th><th>Blocking</th></tr>{rows}</table>")


def _metrics(m: dict[str, Any]) -> str:
    keys = ("total_return", "sharpe_annualized", "deflated_sharpe", "max_drawdown", "breakeven_cost_bps", "n_closed_trades",
            "annual_return", "sharpe", "unsmoothed_sharpe", "dsr")
    cells = "".join(f"<div class='stat'><span class='muted'>{_e(k)}</span><b>{_e(_fmt(m[k]))}</b></div>" for k in keys if m.get(k) is not None)
    return f"<div class='grid'>{cells}</div>" if cells else "<p class='muted'>No metrics: the run stopped before the backtest.</p>"


def _fmt(v: Any) -> str:
    return f"{v:.4g}" if isinstance(v, float) else str(v)


def render_dossier(d: dict[str, Any], checks: list[dict[str, Any]] | None = None) -> str:
    """Render a ``validation-dossier/1`` dict (``checks`` default: those of the embedded certificate summary)."""
    meta = d.get("meta", {})
    verdict = d.get("verdict") or "—"
    rows = checks if checks is not None else (d.get("checks") or [])
    head = "".join(f"<tr><th>{_e(k.replace('_', ' ').capitalize())}</th><td>{_e(v)}</td></tr>" for k, v in meta.items())
    reasons = "".join(f"<li>{_e(r)}</li>" for r in d["summary"].get("reasons", [])) or "<li>No failed or warned checks.</li>"
    actions = "".join(f"<li>{_e(a)}</li>" for a in d["summary"].get("next_actions", []))
    limits = "".join(f"<li>{_e(x)}</li>" for x in d.get("limitations", []))
    env = d.get("environment", {})
    pkgs = ", ".join(f"{k} {v}" for k, v in (env.get("packages") or {}).items() if v)
    alpha = d.get("alpha")
    alpha_html = ""
    if alpha:
        alpha_html = (f"<h2>Signal: alpha report</h2><div class='card'><p>Verdict <span class='pill {_VERDICT_TONE.get(alpha.get('verdict'), 'mute')}'>"
                      f"{_e(alpha.get('verdict'))}</span></p>{_checks_table(alpha.get('checks', []))}</div>")
    live = d.get("live")
    live_html = f"<h2>After launch</h2><div class='card'>{_checks_table(live.get('checks', []))}</div>" if live else ""
    sign = "".join(f"<tr><td>{_e(s['role'])}</td><td></td><td></td><td></td></tr>" for s in d.get("sign_off", []))
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Validation dossier {_e(d.get('dossier_id'))}</title><style>{_CSS}{_EXTRA_CSS}{disclaimer.HTML_CSS}</style></head><body><main>"
        f"<h1>Validation dossier: {_e(meta.get('name', 'strategy'))}</h1>"
        f"<p class='muted'>Dossier <span class='mono'>{_e(d.get('dossier_id'))}</span> · certificate "
        f"<span class='mono'>{_e(d.get('certificate_id'))}</span> · {_e(d.get('generated_at'))}</p>"
        f"<div class='card headline {_VERDICT_TONE.get(verdict, 'mute')}'>Verdict: <b>{_e(verdict)}</b></div>"
        + (f"<h2>Purpose and scope</h2><div class='card'><table>{head}</table></div>" if head else "")
        + f"<h2>Summary</h2><div class='card'><p>Why:</p><ol>{reasons}</ol>"
        + (f"<p>What to do:</p><ol>{actions}</ol>" if actions else "") + "</div>"
        f"<h2>Alpha Readiness Level</h2><div class='card'>{_readiness(d.get('readiness'))}</div>"
        f"<h2>Results</h2><div class='card'>{_metrics(d['summary'].get('metrics', {}))}</div>"
        f"<h2>Checks</h2><div class='card'>{_checks_table(rows)}</div>"
        f"{alpha_html}{live_html}"
        f"<h2>Framework map</h2><div class='card'>{_framework(d['framework'])}</div>"
        f"<h2>Assumptions and limitations</h2><div class='card'><ul>{limits}</ul></div>"
        f"<h2>Reproduce</h2><div class='card'><p class='mono'>{_e(d['reproduce']['command'])}</p>"
        f"<p class='muted small'>Python {_e(env.get('python'))} · {_e(env.get('platform'))} · {_e(pkgs)}</p></div>"
        f"<h2>Sign-off</h2><div class='card'><table class='sign'><tr><th>Role</th><th>Name</th><th>Date</th><th>Signature</th></tr>{sign}</table></div>"
        f"{disclaimer.html_footer()}</main></body></html>\n"
    )


__all__ = ["render_dossier"]
