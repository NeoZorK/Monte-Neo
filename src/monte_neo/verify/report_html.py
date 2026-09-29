"""Render a ``strategy-verdict/1`` certificate as one self-contained HTML page (a tear sheet).

The page has no scripts and loads nothing from the network: charts are inline SVG
(``report_charts``), styles are inline CSS (light, dark and print). Every string taken from the
certificate is escaped, because check summaries can quote user-controlled text such as file names.
"""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any

from monte_neo.verify import report_charts as charts

VERIFY_PAGE = "https://neozork.github.io/Monte-Neo/verify/"
# The report is static: no scripts, no network, no embedding. The policy keeps it that way even if a
# future change lets untrusted text through.
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"
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
svg text{fill:var(--mute);font-size:11px}svg text.cell{fill:var(--fg);font-size:10.5px}ol{margin:0;padding-left:20px}li{margin:4px 0}
.headline{font-size:17px;border-left:5px solid var(--line);padding-left:14px}.headline.bad{border-color:var(--bad);background:var(--card);color:var(--fg)}
.headline.good{border-color:var(--good);background:var(--card);color:var(--fg)}.headline.warn{border-color:var(--warn);background:var(--card);color:var(--fg)}
.headline.note{border-color:var(--note);background:var(--card);color:var(--fg)}
.cats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-top:12px}
.cat{border:1px solid var(--line);border-top:4px solid var(--line);border-radius:10px;padding:10px 12px;background:var(--card)}
.cat.good{border-top-color:var(--good)}.cat.warn{border-top-color:var(--warn)}.cat.bad{border-top-color:var(--bad)}
.cat b{display:block;text-transform:capitalize;font-size:15px}.cat span{font-size:13px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:12px}.two .card{margin-top:0}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;background:var(--line);border-radius:4px;padding:1px 5px;word-break:break-all}
@media (max-width:520px){.two{grid-template-columns:1fr}svg text{font-size:19px}svg text.cell{font-size:15px}}
@media print{@page{margin:12mm}:root{--bg:#fff;--card:#fff;--fg:#111;--mute:#555;--line:#d0d5dd}
body{background:#fff;font-size:12px}main{max-width:none;padding:0}.card,.cat,.stat{break-inside:avoid;box-shadow:none}h2{break-after:avoid}
a{color:inherit;text-decoration:none}.two{grid-template-columns:1fr 1fr}}
"""


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _pct(value: Any) -> str:
    return "—" if not isinstance(value, int | float) or not math.isfinite(value) else f"{value:+.2%}"


def _num(value: Any, digits: int = 2) -> str:
    return "—" if not isinstance(value, int | float) or not math.isfinite(value) else f"{value:.{digits}f}"


def _stat(label: str, value: str) -> str:
    return f'<div class="stat"><span class="muted">{_e(label)}</span><b>{_e(value)}</b></div>'


_CATEGORIES = ("integrity", "lookahead", "economics", "statistics")
_TITLES = {"REJECT": "Rejected", "NEEDS_MORE_EVIDENCE": "Needs more evidence", "PASS_WITH_WARNINGS": "Passed with warnings", "PASS": "Passed"}


def _checks(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in report.get("checks") or [] if isinstance(c, dict)]


def _headline(report: dict[str, Any]) -> str:
    """One sentence that says why the verdict is what it is."""
    verdict = str(report.get("verdict", ""))
    checks = _checks(report)
    failing = [c for c in checks if c.get("status") == "fail"]
    warning = [c for c in checks if c.get("status") == "warn"]
    if verdict == "PASS":
        return "Passed: no look-ahead found, and the edge survives costs, execution delay and selection bias."
    picked = (failing or warning)[:2]
    why = "; ".join(str(c.get("summary", "")) for c in picked)
    rest = len(failing) + len(warning) - len(picked)
    more = f" (and {rest} more)" if rest > 0 else ""
    return f"{_TITLES.get(verdict, verdict)}: {why}{more}." if why else f"{_TITLES.get(verdict, verdict)}."


def _category_cards(report: dict[str, Any]) -> str:
    checks = _checks(report)
    cards = []
    for cat in _CATEGORIES:
        rows = [c for c in checks if c.get("category") == cat]
        if not rows:
            continue
        counts = {s: sum(1 for c in rows if c.get("status") == s) for s in ("pass", "warn", "fail")}
        tone = "bad" if counts["fail"] else "warn" if counts["warn"] else "good"
        text = " · ".join(f"{counts[s]} {s}" for s in ("pass", "warn", "fail") if counts[s]) or "no checks ran"
        cards.append(f'<div class="cat {tone}"><b>{_e(cat)}</b><span class="muted">{_e(text)}</span></div>')
    return f'<div class="cats">{"".join(cards)}</div>' if cards else ""


def _list(items: list[str]) -> str:
    return f"<ul>{''.join(f'<li>{i}</li>' for i in items)}</ul>"


def _evidence(report: dict[str, Any]) -> str:
    """Where a leak shows: the bars where the signal changed, and the source lines the linter flagged."""
    blocks = []
    for c in _checks(report):
        d = c.get("details") if isinstance(c.get("details"), dict) else {}
        if c.get("status") not in ("fail", "warn"):
            continue
        cid = c.get("id")
        items: list[str] = []
        if cid == "lookahead_truncation":
            for m in (d.get("mismatches") or [])[:4]:
                if isinstance(m, dict):
                    items.append(f"cut after bar {_e(m.get('checkpoint'))}: the signal at bar {_e(m.get('bar'))} was {_e(m.get('full'))}, then {_e(m.get('truncated'))}")
        elif cid == "lookahead_perturbation":
            for m in (d.get("mismatches") or [])[:4]:
                if isinstance(m, dict):
                    items.append(f"future rewritten after bar {_e(m.get('checkpoint'))}: the signal changed from bar {_e(m.get('first_changed_bar'))}")
        elif cid == "lookahead_static_lint":
            for f in (d.get("findings") or [])[:8]:
                if isinstance(f, dict):
                    items.append(f"line {_e(f.get('line'))} <b>{_e(f.get('rule'))}</b>: {_e(f.get('message'))}<br><code>{_e(f.get('snippet'))}</code>")
        elif cid == "implausible_accuracy":
            items.append(f"next-bar hit rate {_num(d.get('hit_rate'), 3)} over {_e(d.get('active_bars'))} bars (z {_num(d.get('z_score'), 1)}); a real edge rarely exceeds {_num(d.get('max_hit_rate'), 2)}")
        elif cid == "external_data":
            items += [f"read {_e(f)}" for f in (d.get("files") or [])[:5]] + [f"connected to {_e(h)}" for h in (d.get("connections") or [])[:5]]
        elif cid == "data_quality":
            for key in ("spike_examples", "split_examples"):
                for m in (d.get(key) or [])[:3]:
                    if isinstance(m, dict):
                        items.append(f"{'spike' if key.startswith('spike') else 'split-like jump'} at bar {_e(m.get('bar'))}" + (f" ({_e(m.get('symbol'))})" if m.get("symbol") else ""))
        if items:
            blocks.append(f"<p><span class='pill {_STATUS_TONE.get(c.get('status'), 'mute')}'>{_e(c.get('status'))}</span> <span class='mono'>{_e(cid)}</span></p>{_list(items)}")
    return f"<h2>Evidence</h2><div class='card'>{''.join(blocks)}</div>" if blocks else ""


def _trade_stats(block: Any) -> str:
    if not isinstance(block, dict) or not block:
        return ""
    stats = [
        _stat("closed trades", str(block.get("n", "—"))),
        _stat("win rate", _num(100 * block["win_rate"], 1) + "%" if isinstance(block.get("win_rate"), int | float) else "—"),
        _stat("profit factor", _num(block.get("profit_factor"))),
        _stat("average win", _pct(block.get("avg_win"))),
        _stat("average loss", _pct(block.get("avg_loss"))),
        _stat("best trade", _pct(block.get("best"))),
        _stat("worst trade", _pct(block.get("worst"))),
        _stat("average hold", f"{_num(block.get('avg_hold_bars'), 1)} bars"),
        _stat("longest win streak", str(block.get("max_consecutive_wins", "—"))),
        _stat("longest loss streak", str(block.get("max_consecutive_losses", "—"))),
    ]
    return f"<h2>Trades</h2><div class='card grid'>{''.join(stats)}</div>"


def _figure(title: str, svg: str, note: str = "") -> str:
    return f"<div class='card'><b>{_e(title)}</b>{svg}" + (f"<p class='muted'>{_e(note)}</p>" if note else "") + "</div>" if svg else ""


def _charts_section(report: dict[str, Any]) -> str:
    c = report.get("charts") if isinstance(report.get("charts"), dict) else {}
    rolling = c.get("rolling_sharpe") if isinstance(c.get("rolling_sharpe"), dict) else {}
    figures = [
        _figure("Return distribution", charts.returns_histogram_chart(c.get("returns_hist")), "Per-bar returns after warm-up, bars with a change only."),
        _figure("Rolling Sharpe", charts.rolling_sharpe_chart(rolling), f"Annualized, trailing window of {rolling.get('window', '')} bars."),
        _figure("Timing test", charts.timing_chart(c.get("timing")),
                "Net return of 200 time-shifted copies of the same positions. A real signal beats most of them; a strategy that only holds the market does not."),
        _figure("Sensitivity to costs", charts.cost_chart(c.get("cost_curve")), "Net return as the per-side trading cost grows."),
    ]
    monthly = charts.monthly_heatmap(c.get("monthly"))
    top = _figure("Monthly returns", monthly) if monthly else ""
    pairs = [f for f in figures if f]
    grid = f"<div class='two'>{''.join(pairs)}</div>" if pairs else ""
    return f"{top}{grid}"


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
        f"neighbouring parameters keep {f'{ratio:.0%}' if isinstance(ratio, int | float) else '—'} of the best Sharpe.</p>"
        f"{charts.grid_heatmap(grid)}</div>"
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
        f'Check it on the <a href="{VERIFY_PAGE}" rel="noopener noreferrer">verification page</a> or with '
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
        f"<meta http-equiv='Content-Security-Policy' content=\"{CSP}\">"
        "<meta name='referrer' content='no-referrer'>"
        f"<title>Monte-Neo verdict {_e(verdict)} · {_e(report.get('certificate_id', ''))}</title>"
        f"<style>{_CSS}</style></head><body><main>"
        f"<h1>Monte-Neo strategy verdict <span class='pill verdict {_VERDICT_TONE.get(verdict, 'mute')}'>{_e(verdict)}</span></h1>"
        f"<p class='muted'>Certificate <span class='mono'>{_e(report.get('certificate_id', ''))}</span> · "
        f"engine {_e(repro.get('engine_version', ''))} · {_e(report.get('generated_at', ''))}</p>"
        f"<div class='card headline {_VERDICT_TONE.get(verdict, 'mute')}'>{_e(_headline(report))}</div>"
        f"{_category_cards(report)}"
        f"<div class='card'>{signed}</div>"
        f"<h2>Summary</h2><div class='card grid'>{''.join(stats)}</div>"
        f"<h2>Equity</h2><div class='card'>{charts.equity_chart(report.get('series') or {})}</div>"
        + _charts_section(report)
        + _trade_stats((report.get("charts") or {}).get("trade_stats") if isinstance(report.get("charts"), dict) else None)
        + (f"<h2>What to fix</h2><div class='card'><ol>{actions}</ol></div>" if actions else "")
        + _evidence(report)
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
