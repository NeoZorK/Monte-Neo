"""Static, read-only dashboard built from the journal: one self-contained HTML file (inline SVG, no scripts, no CDN).

``build(journal_path, out)`` writes ``out/index.html``; ``serve(out, host, port)`` serves that folder only (GET and HEAD,
no writes). Every number on the page comes from the journal through :mod:`monte_neo.deploy.metrics`; the page shows the
chain check and the head hash, so a screenshot can be matched to the journal later.
"""

from __future__ import annotations

import functools
import html
import http.server
from pathlib import Path
from typing import Any

from monte_neo.deploy import account, metrics
from monte_neo.deploy import journal as jr
from monte_neo.disclaimer import html_footer
from monte_neo.verify.report_html import CSP


def _pct(x: float | None, d: int = 2) -> str:
    return "n/a" if x is None else f"{x * 100:.{d}f} %"


def _num(x: float | None, d: int = 2) -> str:
    return "n/a" if x is None else f"{x:,.{d}f}"


def _esc(x: Any) -> str:
    return html.escape(str(x))


def _svg_lines(series: dict[str, list[float]], colors: dict[str, str], w: int = 760, h: int = 220) -> str:
    vals = [v for s in series.values() for v in s]
    if len(vals) < 2:
        return '<p class="muted">Not enough marks yet.</p>'
    lo, hi = min(vals), max(vals)
    hi = hi if hi > lo else lo + 1.0
    pad = 8
    n = max(len(s) for s in series.values())
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" class="chart">']
    for frac in (0, 0.5, 1):
        y = pad + (h - 2 * pad) * frac
        out.append(f'<line x1="0" x2="{w}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="2" y="{y - 2:.1f}" class="axis">{hi - (hi - lo) * frac:,.2f}</text>')
    for name, s in series.items():
        if len(s) < 2:
            continue
        pts = " ".join(f"{i / (n - 1) * w:.1f},{pad + (hi - v) / (hi - lo) * (h - 2 * pad):.1f}" for i, v in enumerate(s))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{colors.get(name, "currentColor")}" stroke-width="2"/>')
    out.append("</svg>")
    legend = " ".join(f'<span class="key" style="--c:{colors.get(k, "currentColor")}">{_esc(k)}</span>' for k in series)
    return "".join(out) + f'<div class="legend">{legend}</div>'


CSS = """
:root{--bg:#f6f7f9;--fg:#141922;--card:#fff;--muted:#5b6573;--line:#d9dee5;--ok:#1a7f4b;--bad:#b42318;--wait:#8a6d00}
@media (prefers-color-scheme:dark){:root{--bg:#0f1319;--fg:#e8ecf2;--card:#171c24;--muted:#9aa3ad;--line:#2a313c;--ok:#4cc38a;--bad:#ff6b5e;--wait:#e3b341}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,Helvetica,Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:16px}h1{font-size:20px;margin:4px 0 2px}h2{font-size:15px;margin:0 0 8px}
.muted{color:var(--muted)}.grid{stroke:var(--line)}.axis{fill:var(--muted);font-size:10px}.chart{width:100%;height:auto}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:12px 0}
.card,section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:10px}
.card{margin:0}.k{color:var(--muted);font-size:12px}.v{font-size:20px;font-weight:600}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left}
.ok{color:var(--ok)}.bad{color:var(--bad)}.wait{color:var(--wait)}code{font-size:12px;word-break:break-all}
.legend{display:flex;gap:14px;font-size:12px;color:var(--muted)}.key::before{content:"";display:inline-block;width:10px;height:3px;background:var(--c);margin-right:5px;vertical-align:middle}
"""


def render(entries: list[dict[str, Any]], chain: dict[str, Any]) -> str:
    start = next((e["body"] for e in entries if e["kind"] == "start"), {})
    s = metrics.summary(entries)
    paper, test = account.replay(entries, "paper"), account.replay(entries, "testnet")
    paper_name = "paper (mainnet prices, modelled costs)"
    navs = {paper_name: [m["nav"] for m in paper["marks"]]}
    if s["testnet_nav"] is not None:
        navs["testnet (demo fills)"] = [m["nav"] for m in test["marks"]]
    colors = {paper_name: "#3b6fd8", "testnet (demo fills)": "#d9822b"}
    last_sig = next((e["body"] for e in reversed(entries) if e["kind"] == "signal"), None)
    devs = [e for e in entries if e["kind"] == "deviation"]
    anchors = [e["body"] for e in entries if e["kind"] == "anchor" and "skipped" not in e["body"]]
    last_ts = entries[-1]["ts"] if entries else "n/a"
    cert = start.get("certificate") or {}
    strat = start.get("strategy") or {}
    status = "KILLED" if s["killed"] else ("RUNNING" if s["days"] else "NOT STARTED")
    cls = "bad" if s["killed"] else ("ok" if s["days"] else "wait")
    sig_rows = ""
    if last_sig:
        sig_rows = "".join(f"<tr><td>{_esc(sym)}</td><td>{_pct(w, 1)}</td></tr>" for sym, w in sorted(last_sig["weights"].items()))
    pos = "".join(f"<tr><td>{_esc(k)}</td><td>{_num(v, 6)}</td></tr>" for k, v in sorted(paper["positions"].items())) or "<tr><td colspan=2 class=muted>flat</td></tr>"
    dev_html = "".join(f"<li>{_esc(e['ts'])}: {_esc(e['body'].get('why', ''))}</li>" for e in devs) or "<li class=muted>none</li>"
    warn_html = "".join(f"<li>{_esc(w)}</li>" for w in start.get("warnings", [])) or "<li class=muted>none</li>"
    title = "Monte-Neo deploy: forward record"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="{CSP}"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300"><title>{title}</title><style>{CSS}</style></head><body><main>
<h1>{title}</h1>
<div class="muted">Strategy <code>{_esc(strat.get('file', 'n/a'))}</code> · mode {_esc(start.get('mode', 'n/a'))} · rebalance {_esc(start.get('rebalance', 'n/a'))} · first day {_esc(start.get('first_day', 'n/a'))} · last entry {_esc(last_ts)} UTC</div>
<div class="cards">
<div class="card"><div class="k">Status</div><div class="v {cls}">{status}</div></div>
<div class="card"><div class="k">Paper NAV</div><div class="v">{_num(s['paper_nav'])}</div></div>
<div class="card"><div class="k">Return</div><div class="v">{_pct(s['paper_return'])}</div></div>
<div class="card"><div class="k">Sharpe (2x costs)</div><div class="v">{_num(s['sharpe_costs_x2'])}</div></div>
<div class="card"><div class="k">Max drawdown</div><div class="v">{_pct(s['max_drawdown'])}</div></div>
<div class="card"><div class="k">Days recorded</div><div class="v">{s['days']}</div></div>
</div>
{'<section><h2 class="bad">Kill switch active: trading stopped</h2></section>' if s['killed'] else ''}
<section><h2>Net asset value</h2>{_svg_lines(navs, colors)}</section>
<section><h2>Risk</h2><p class="muted">Sharpe {_num(s['sharpe'])} · worst week {_pct(s['worst_week'])} · one-day VaR 95 {_pct(s['one_day_var_95'])} · ES 95 {_pct(s['one_day_es_95'])} · tracking error demo vs paper {_pct(s['tracking_error'])} a year · kill switch at {_pct(start.get('kill_drawdown'))}</p></section>
<section><h2>Eligibility</h2><p>Certificate <code>{_esc(cert.get('id', 'n/a'))}</code> · verdict {_esc(cert.get('verdict', 'n/a'))} · ARL {_esc(cert.get('arl', 'n/a'))} · strategy SHA-256 <code>{_esc(strat.get('sha256', 'n/a'))}</code></p><ul>{warn_html}</ul>
<p class="muted">Forward-return verdict (latest certify): {_esc(s['forward_verdict'] or 'not certified yet')}</p></section>
<section><h2>Last signal</h2>{'<table><tr><th>Symbol</th><th>Weight of capital</th></tr>' + sig_rows + '</table>' if last_sig else '<p class="muted">No signal yet (waiting for the first rebalance day).</p>'}</section>
<section><h2>Paper positions</h2><table>{pos}</table></section>
<section><h2>Deviations from the protocol</h2><ul>{dev_html}</ul></section>
<section><h2>Journal integrity</h2><p class="{'ok' if chain['ok'] else 'bad'}">{'chain intact' if chain['ok'] else 'CHAIN BROKEN: ' + _esc(chain['problem'])} · {chain['entries']} entries · {len(anchors)} RFC 3161 anchors</p>
<p class="muted">Head <code>{_esc(chain['head'])}</code></p></section>
<p class="muted">Forward record on Binance demo (testnet) execution and mainnet market data. Not live trading and not investment advice.</p>
{html_footer()}</main></body></html>"""


def build(journal_path: Path | str, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    entries = list(jr.Journal(Path(journal_path)).entries())
    page = render(entries, jr.verify(journal_path))
    tmp = out / "index.html.tmp"
    tmp.write_text(page, encoding="utf-8")
    tmp.replace(out / "index.html")
    return out / "index.html"


class _ReadOnly(http.server.SimpleHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        self.send_error(405)

    do_PUT = do_DELETE = do_PATCH = do_POST  # noqa: N815

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass


def make_server(out: Path, host: str = "127.0.0.1", port: int = 8787) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(_ReadOnly, directory=str(out))
    return http.server.ThreadingHTTPServer((host, port), handler)


def serve(out: Path, host: str = "127.0.0.1", port: int = 8787) -> None:
    """Serve ``out`` read-only. Use ``--host 0.0.0.0`` to reach it from the LAN (put it behind a firewall)."""
    with make_server(out, host, port) as srv:
        print(f"dashboard on http://{host}:{port}/ (read-only, serving {out})", flush=True)
        srv.serve_forever()
