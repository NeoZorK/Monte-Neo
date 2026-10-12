"""``repair-report.html``: what was wrong, what was changed and why, what the lockbox said. One page, no scripts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from monte_neo import disclaimer
from monte_neo.verify.report_html import _CSS, CSP, _e

_TONE = {"REPAIRED": "good", "REPAIRED_NO_EDGE": "warn", "NOT_REPAIRABLE": "bad", "NOTHING_TO_REPAIR": "mute"}


def _row(label: str, s: dict[str, Any] | None) -> str:
    if not s:
        return ""
    ret = s.get("total_return")
    sharpe = s.get("sharpe")
    return (f"<tr><td>{_e(label)}</td><td>{_e(s.get('verdict'))}</td><td>{'' if ret is None else f'{ret:+.1%}'}</td>"
            f"<td>{'' if sharpe is None else f'{sharpe:.2f}'}</td><td class='mono'>{_e(', '.join(s.get('failed', [])))}</td></tr>")


def render(rep: dict[str, Any]) -> str:
    """Render a ``repair-report/1`` dict."""
    o = rep["outcome"]
    table = (_row("Before", rep.get("original")) + _row("After (all data)", rep.get("final"))
             + _row("Lockbox (opened once)", rep.get("lockbox")))
    corr = "".join(f"<li><b>{_e(c['id'])}</b> {_e(c.get('rule'))}: {_e(c.get('why'))}</li>" for c in rep.get("corrections", []))
    cands = "".join(
        f"<tr><td>{_e(c['id'])}</td><td class='mono'>{_e(c['steps'])}</td><td>{_e(c['why'])}</td><td>{_e(c['dev_defects'])}</td>"
        f"<td>{'chosen' if rep.get('chosen') and c['steps'] == rep['chosen']['steps'] else ''}</td></tr>"
        for c in rep.get("candidates", [])
    )
    needs = "".join(f"<li>{_e(b)}</li>" for b in rep.get("not_repairable", []))
    dev = rep.get("dev") or {}
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<meta http-equiv='Content-Security-Policy' content=\"{CSP}\">"
        f"<title>Repair report</title><style>{_CSS}{disclaimer.HTML_CSS}</style></head><body><main>"
        f"<h1>Repair: {_e(rep.get('strategy'))}</h1>"
        f"<div class='card headline {_TONE[o]}'><b>{_e(o)}</b> — {_e(rep['headline'])}</div>"
        f"<h2>Before and after</h2><div class='card'><table><tr><th></th><th>Verdict</th><th>Net return</th><th>Sharpe</th><th>Failed checks</th></tr>{table}</table>"
        + (f"<p class='muted'>Repairs were chosen on the history until {_e(dev.get('until', '')[:10])} by the number of defects "
           f"({_e(dev.get('baseline_defects'))} → {_e(dev.get('chosen_defects'))}), never by return. Trials counted: {_e(dev.get('trials'))}.</p>" if dev else "")
        + "</div>"
        + (f"<h2>Corrections (no parameters)</h2><div class='card'><ul>{corr}</ul></div>" if corr else "")
        + (f"<h2>Candidates</h2><div class='card'><table><tr><th>Id</th><th>Steps</th><th>Why</th><th>Defects</th><th></th></tr>{cands}</table></div>" if cands else "")
        + (f"<h2>Needs you</h2><div class='card'><ul>{needs}</ul></div>" if needs else "")
        + "<h2>Files</h2><div class='card'><p class='mono'>strategy.repaired.py · repair.diff · certificate.json · repair-report.json</p>"
        "<p class='muted'>The original strategy file is never changed.</p></div>"
        f"{disclaimer.html_footer()}</main></body></html>\n"
    )


def write_html(rep: dict[str, Any], out_dir: str | Path) -> Path:
    """Write ``repair-report.html`` into ``out_dir``."""
    path = Path(out_dir) / "repair-report.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(rep), encoding="utf-8")
    return path


__all__ = ["render", "write_html"]
