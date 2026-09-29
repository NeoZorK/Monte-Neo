"""Render a ``strategy-verdict/1`` certificate as one self-contained HTML page.

The page has no scripts and loads nothing from the network: charts are inline SVG,
styles are inline CSS (light and dark). Every string taken from the certificate is
escaped, because check summaries can quote user-controlled text such as file names.
"""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any

VERIFY_PAGE = "https://neozork.github.io/Monte-Neo/verify/"
_VERDICT_TONE = {"PASS": "good", "PASS_WITH_WARNINGS": "warn", "NEEDS_MORE_EVIDENCE": "note", "REJECT": "bad"}
_STATUS_TONE = {"pass": "good", "warn": "warn", "fail": "bad", "skip": "mute", "info": "note"}

_CSS = """
:root{--bg:#f7f8fa;--card:#fff;--fg:#1d2330;--mute:#667085;--line:#e4e7ec;--good:#177245;--good-bg:#e7f6ee;
--warn:#8a5a00;--warn-bg:#fff4dc;--bad:#b42318;--bad-bg:#fdecea;--note:#3548a8;--note-bg:#eaeefd;--strat:#2f6fde;--bench:#98a2b3}
@media (prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#171b23;--fg:#e6e9ef;--mute:#98a2b3;--line:#2a303c;
--good:#5bd08f;--good-bg:#12291d;--warn:#f2c14e;--warn-bg:#2d2412;--bad:#ff7b6e;--bad-bg:#331714;--note:#9fb0ff;--note-bg:#1a2140;
--strat:#6ea1ff;--bench:#667085}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px 48px}h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-top:12px;overflow-x:auto}
.muted{color:var(--mute)}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;word-break:break-all}
.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-weight:600;font-size:13px}
.good{color:var(--good);background:var(--good-bg)}.warn{color:var(--warn);background:var(--warn-bg)}
.bad{color:var(--bad);background:var(--bad-bg)}.note{color:var(--note);background:var(--note-bg)}.mute{color:var(--mute);background:var(--line)}
.verdict{font-size:18px;padding:4px 14px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.stat{border:1px solid var(--line);border-radius:10px;padding:10px 12px}.stat b{display:block;font-size:18px}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:13px;color:var(--mute);font-weight:600}th.num{text-align:right}td.mono{word-break:normal;white-space:nowrap}td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.legend span{margin-right:16px}.sw{display:inline-block;width:12px;height:3px;vertical-align:middle;margin-right:6px}
svg text{fill:var(--mute);font-size:11px}ol{margin:0;padding-left:20px}li{margin:4px 0}
"""


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _pct(value: Any) -> str:
    return "—" if not isinstance(value, int | float) or not math.isfinite(value) else f"{value:+.2%}"


def _num(value: Any, digits: int = 2) -> str:
    return "—" if not isinstance(value, int | float) or not math.isfinite(value) else f"{value:.{digits}f}"


def _stat(label: str, value: str) -> str:
    return f'<div class="stat"><span class="muted">{_e(label)}</span><b>{_e(value)}</b></div>'


def _polyline(values: list[float], lo: float, hi: float, width: int, height: int, pad: int) -> str:
    span = hi - lo or 1.0
    n = max(len(values) - 1, 1)
    pts = (
        f"{pad + (width - 2 * pad) * i / n:.1f},{height - pad - (height - 2 * pad) * (v - lo) / span:.1f}"
        for i, v in enumerate(values)
    )
    return " ".join(pts)


def _equity_chart(series: dict[str, Any]) -> str:
    equity = [float(v) for v in series.get("equity") or []]
    bench = [float(v) for v in series.get("benchmark") or []]
    if len(equity) < 2:
        return '<p class="muted">No equity series in this certificate.</p>'
    width, height, pad = 960, 260, 34
    lo = min(equity + bench)
    hi = max(equity + bench)
    times = series.get("time") or []
    first = (times[0] if times else f"bar {series['bar'][0]}")[:10]
    last = (times[-1] if times else f"bar {series['bar'][-1]}")[:10]
    peak, drawdown = equity[0], []
    for v in equity:
        peak = max(peak, v)
        drawdown.append(v / peak - 1.0 if peak > 0 else 0.0)
    dd_lo = min(drawdown) or -1e-9
    dd_h = 90
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Equity: strategy and buy and hold">'
        f'<polyline fill="none" stroke="var(--bench)" stroke-width="1.5" points="{_polyline(bench, lo, hi, width, height, pad)}"/>'
        f'<polyline fill="none" stroke="var(--strat)" stroke-width="2" points="{_polyline(equity, lo, hi, width, height, pad)}"/>'
        f'<text x="4" y="{pad}">{hi:.2f}×</text><text x="4" y="{height - pad}">{lo:.2f}×</text>'
        f'<text x="{pad}" y="{height - 8}">{_e(first)}</text>'
        f'<text x="{width - pad}" y="{height - 8}" text-anchor="end">{_e(last)}</text></svg>'
        f'<svg viewBox="0 0 {width} {dd_h}" width="100%" role="img" aria-label="Drawdown">'
        f'<polyline fill="none" stroke="var(--bad)" stroke-width="1.5" points="{_polyline(drawdown, dd_lo, 0.0, width, dd_h, 14)}"/>'
        f'<text x="4" y="14">0%</text><text x="4" y="{dd_h - 4}">{dd_lo:.1%}</text></svg>'
        '<div class="legend muted"><span><i class="sw" style="background:var(--strat)"></i>strategy</span>'
        '<span><i class="sw" style="background:var(--bench)"></i>buy &amp; hold</span>'
        '<span><i class="sw" style="background:var(--bad)"></i>strategy drawdown</span></div>'
    )


def _checks_table(checks: list[dict[str, Any]]) -> str:
    rows = "".join(
        f'<tr><td class="mono">{_e(c.get("id"))}</td><td>{_e(c.get("category"))}</td>'
        f'<td><span class="pill {_STATUS_TONE.get(c.get("status"), "mute")}">{_e(c.get("status"))}</span></td>'
        f"<td>{_e(c.get('summary'))}</td></tr>"
        for c in checks
    )
    return f"<table><tr><th>check</th><th>category</th><th>status</th><th>summary</th></tr>{rows}</table>"


def _periods_table(breakdown: dict[str, Any]) -> str:
    periods = breakdown.get("periods") or []
    if not periods:
        return ""
    rows = "".join(
        f"<tr><td>{_e(p['period'])}</td><td class='num'>{p['bars']}</td><td class='num'>{_pct(p['return'])}</td>"
        f"<td class='num'>{_pct(p['benchmark_return'])}</td><td class='num'>{_num(p['sharpe_annualized'])}</td>"
        f"<td class='num'>{_num(100 * p['exposure'], 0)}%</td></tr>"
        for p in periods
    )
    head = (
        "<tr><th>period</th><th class='num'>bars</th><th class='num'>return</th><th class='num'>buy &amp; hold</th>"
        "<th class='num'>Sharpe</th><th class='num'>exposure</th></tr>"
    )
    return f'<h2>By period ({_e(breakdown.get("frequency", ""))})</h2><div class="card"><table>{head}{rows}</table></div>'


def _regimes_table(breakdown: dict[str, Any]) -> str:
    regimes = breakdown.get("regimes") or {}
    if not regimes:
        return ""
    rows = "".join(
        f"<tr><td>{_e(name)}</td><td class='num'>{_num(100 * r['share'], 0)}%</td><td class='num'>{_pct(r['return'])}</td>"
        f"<td class='num'>{_pct(r['market_return'])}</td><td class='num'>{_num(r['sharpe_annualized'])}</td></tr>"
        for name, r in regimes.items()
    )
    head = (
        "<tr><th>market regime</th><th class='num'>share of bars</th><th class='num'>strategy</th>"
        "<th class='num'>market</th><th class='num'>Sharpe</th></tr>"
    )
    note = (
        f'<p class="muted">Regime of a bar: the market\'s trailing return and volatility over the previous '
        f'{_e(breakdown.get("window", ""))} bars.</p>'
    )
    return f'<h2>By market regime</h2><div class="card"><table>{head}{rows}</table>{note}</div>'


def _grid_section(grid: dict[str, Any] | None) -> str:
    if not grid:
        return ""
    wf = grid.get("walk_forward") or {}
    plateau = grid.get("plateau") or {}
    ratio = plateau.get("median_ratio")
    return (
        '<h2>Parameter search</h2><div class="card">'
        f"<p>{_e(grid.get('n_combos'))} combinations; best <span class='mono'>{_e(grid.get('best_params'))}</span>.</p>"
        f"<p>Walk-forward out-of-sample Sharpe per bar: {_num(wf.get('oos_sharpe'), 4)}; "
        f"parameter stability {_num(wf.get('param_stability'))}; "
        f"neighbouring parameters keep {'—' if ratio is None else f'{ratio:.0%}'} of the best Sharpe.</p></div>"
    )


def render_html(report: dict[str, Any]) -> str:
    """The certificate as a standalone HTML page (no scripts, no network)."""
    verdict = str(report.get("verdict", ""))
    m = report.get("metrics") or {}
    repro = report.get("reproducibility") or {}
    sig = report.get("signature")
    bench = report.get("benchmark") or {}
    breakdown = report.get("breakdown") or {}
    universe = repro.get("universe")
    stats = [
        _stat("net return", _pct(m.get("total_return"))),
        _stat("Sharpe (annualized)", _num(m.get("sharpe_annualized"))),
        _stat("max drawdown", _pct(-abs(m["max_drawdown"])) if isinstance(m.get("max_drawdown"), int | float) else "—"),
        _stat("closed trades", str(m.get("n_closed_trades", "—"))),
        _stat("Deflated Sharpe", _num(m.get("deflated_sharpe"), 3)),
        _stat("timing p-value", _num(m.get("timing_p_value"), 3)),
        _stat("buy & hold return", _pct(bench.get("total_return", m.get("benchmark_total_return")))),
        _stat("buy & hold Sharpe", _num(bench.get("sharpe_annualized", m.get("benchmark_sharpe_annualized")))),
        _stat("break-even cost", f"{_num(m.get('breakeven_cost_bps'), 1)} bps"),
        _stat("positions", str(m.get("positions", "—"))),
    ]
    if universe:
        stats.append(_stat("symbols", str(universe.get("symbols"))))
    signed = (
        f'Signed with Ed25519 key <span class="mono">{_e(sig.get("key_id"))}</span>. '
        f'Check it on the <a href="{VERIFY_PAGE}">verification page</a> or with '
        '<span class="mono">monte-neo verify --check-signature CERT --public-key KEY.pub</span>.'
        if isinstance(sig, dict)
        else "Not signed. Sign with <span class='mono'>monte-neo verify ... --sign KEY</span> to prove who issued it."
    )
    model = repro.get("model") or {}
    actions = "".join(f"<li>{_e(a)}</li>" for a in report.get("next_actions") or [])
    settings = repro.get("settings") or {}
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Monte-Neo verdict {_e(verdict)} · {_e(report.get('certificate_id', ''))}</title>"
        f"<style>{_CSS}</style></head><body><main>"
        f"<h1>Monte-Neo strategy verdict <span class='pill verdict {_VERDICT_TONE.get(verdict, 'mute')}'>{_e(verdict)}</span></h1>"
        f"<p class='muted'>Certificate <span class='mono'>{_e(report.get('certificate_id', ''))}</span> · "
        f"engine {_e(repro.get('engine_version', ''))} · {_e(report.get('generated_at', ''))}</p>"
        f"<div class='card'>{signed}</div>"
        f"<h2>Summary</h2><div class='card grid'>{''.join(stats)}</div>"
        f"<h2>Equity</h2><div class='card'>{_equity_chart(report.get('series') or {})}</div>"
        + (f"<h2>What to fix</h2><div class='card'><ol>{actions}</ol></div>" if actions else "")
        + f"<h2>Checks</h2><div class='card'>{_checks_table(report.get('checks') or [])}</div>"
        + _periods_table(breakdown)
        + _regimes_table(breakdown)
        + _grid_section(report.get("grid"))
        + "<h2>Reproduce</h2><div class='card'>"
        f"<p>Costs: {_num(model.get('commission_bps'))} bps commission + {_num(model.get('slippage_bps'))} bps slippage per side; "
        f"fills at the next bar's {'open' if model.get('fill_policy') == 'next_bar_open' else 'close'}; "
        f"{_e(model.get('side_mode', ''))}; warm-up {_e(model.get('warmup_bars', ''))} bars; "
        f"n_trials {_e(repro.get('n_trials', ''))}; min_trades {_e(settings.get('min_trades', '—'))}.</p>"
        f"<p class='mono'>data {_e(repro.get('data_sha256', ''))}<br>signals {_e(repro.get('signals_sha256', ''))}"
        f"<br>source {_e(repro.get('source_sha256', ''))}</p>"
        "<p>Re-run with the same data and code: <span class='mono'>monte-neo verify --recheck CERT --ohlcv DATA "
        "--strategy STRATEGY.py</span></p></div>"
        f"<p class='muted'>{_e(report.get('disclaimer', ''))}</p>"
        "</main></body></html>\n"
    )


def write_html(report: dict[str, Any], path: str | Path) -> Path:
    """Write :func:`render_html` to ``path`` (UTF-8) and return the path."""
    out = Path(path)
    out.write_text(render_html(report), encoding="utf-8")
    return out


__all__ = ["render_html", "write_html"]
