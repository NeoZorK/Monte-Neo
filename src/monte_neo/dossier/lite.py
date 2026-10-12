"""Dossier lite: one printable page in plain words for a family office or a reader who is not a quant."""

from __future__ import annotations

from typing import Any

from monte_neo import disclaimer
from monte_neo.verify.report_html import _CSS, _VERDICT_TONE, CSP, _e

_SENTENCE = {
    "PASS": "The independent checks found no problem with how this backtest was built.",
    "PASS_WITH_WARNINGS": "The independent checks found no fatal problem, but some warnings need a person to look at them.",
    "NEEDS_MORE_EVIDENCE": "The checks could not confirm this result: more evidence is needed before anyone relies on it.",
    "REJECT": "The independent checks found a serious problem: do not rely on this result.",
}
_KEYS = (
    ("Net return", ("total_return", "annual_return"), "pct"),
    ("Sharpe ratio", ("sharpe_annualized", "sharpe"), "num"),
    ("Worst fall (max drawdown)", ("max_drawdown",), "pct"),
    ("Deflated Sharpe (chance it is luck, lower is better)", ("deflated_sharpe", "dsr"), "p"),
    ("Trades", ("n_closed_trades", "n_trades"), "int"),
)
_LITE_CSS = (".box{border:2px solid var(--fg);border-radius:10px;padding:12px 14px;margin:12px 0;font-size:14px}"
             "h1+.box{margin-top:16px}.big{font-size:19px}")


def _value(m: dict[str, Any], names: tuple[str, ...], kind: str) -> str | None:
    raw = next((m[n] for n in names if isinstance(m.get(n), (int, float))), None)
    if raw is None:
        return None
    if kind == "pct":
        return f"{raw * 100:.1f}%"
    if kind == "int":
        return str(int(raw))
    if kind == "p":
        return f"{(1 - raw) * 100:.0f}%" if 0 <= raw <= 1 else f"{raw:.2f}"
    return f"{raw:.2f}"


def key_numbers(dossier: dict[str, Any]) -> list[tuple[str, str]]:
    """At most five (label, value) pairs from the metrics that exist."""
    m = dossier.get("summary", {}).get("metrics", {})
    out = [(label, v) for label, names, kind in _KEYS if (v := _value(m, names, kind)) is not None]
    return out[:5]


def top_reasons(dossier: dict[str, Any], n: int = 3) -> list[str]:
    """The ``n`` most important reasons, failed checks first, as ``check id: summary``."""
    checks = dossier.get("checks") or []
    ranked = [c for c in checks if c.get("status") == "fail"] + [c for c in checks if c.get("status") == "warn"]
    reasons = [f"{c['summary']} ({c['id'].replace('_', ' ')})" for c in ranked]
    return (reasons or list(dossier.get("summary", {}).get("reasons", [])))[:n]


def render_lite(dossier: dict[str, Any]) -> str:
    """Render a ``validation-dossier/1`` as one plain-language, printable HTML page (no scripts)."""
    verdict = dossier.get("verdict") or "-"
    meta = dossier.get("meta", {})
    ready = dossier.get("readiness") or {}
    nums = "".join(f"<div class='stat'><span class='muted'>{_e(k)}</span><b>{_e(v)}</b></div>" for k, v in key_numbers(dossier))
    reasons = top_reasons(dossier)
    why = "".join(f"<li>{_e(r)}</li>" for r in reasons) or "<li>No check failed or raised a warning.</li>"
    limits = dossier.get("limitations", [])
    # the three standing limits say what a verifier can never tell: they are the most useful for a non-professional
    not_tell = limits[-4:-1] if len(limits) >= 4 else limits[:3]
    cant = "".join(f"<li>{_e(x)}</li>" for x in not_tell)
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<meta http-equiv='Content-Security-Policy' content=\"{CSP}\">"
        f"<title>Plain-language summary {_e(dossier.get('dossier_id'))}</title><style>{_CSS}{_LITE_CSS}{disclaimer.HTML_CSS}</style></head><body><main>"
        f"<h1>Plain-language summary: {_e(meta.get('name', 'strategy'))}</h1>"
        f"<div class='box'><b>Important.</b> {_e(disclaimer.FULL)}</div>"
        f"<div class='card headline {_VERDICT_TONE.get(verdict, 'mute')}'><span class='big'>Verdict: <b>{_e(verdict)}</b>.</span> "
        f"{_e(_SENTENCE.get(verdict, ''))}</div>"
        f"<p><b>Readiness:</b> {_e(ready.get('summary', 'not assessed'))}. This rates the evidence, not the investment.</p>"
        f"<h2>Key numbers</h2><div class='grid'>{nums or '<p class=muted>No numbers: the run stopped early.</p>'}</div>"
        f"<h2>Main reasons</h2><div class='card'><ol>{why}</ol></div>"
        f"<h2>What this does not tell you</h2><div class='card'><ul>{cant}</ul></div>"
        f"<h2>How to reproduce</h2><div class='card'><p class='mono'>{_e(dossier.get('reproduce', {}).get('command', ''))}</p>"
        f"<p class='muted'>Certificate <span class='mono'>{_e(dossier.get('certificate_id'))}</span>. "
        "Anyone with the same data and code gets the same result.</p></div>"
        f"{disclaimer.html_footer()}</main></body></html>\n"
    )


__all__ = ["key_numbers", "render_lite", "top_reasons"]
