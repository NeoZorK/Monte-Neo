"""The evidence report: one self-contained HTML file plus a manifest of every number.

Every number comes from the journal, from public Binance daily bars, or from the latest Monte-Neo certificate; nothing
is typed by hand. ``build`` writes ``report.html`` and ``report_manifest.json`` (the numbers and their SHA-256);
``verify`` recomputes the manifest from scratch and lists any difference. Stress replays run the same frozen strategy on
historical windows (configurable) and are labelled as backtest replays, never mixed with the recorded forward period.
Print to PDF from a browser (the page has print styles).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import math
from pathlib import Path
from typing import Any

from monte_neo.deploy import account, metrics, plugin, runner
from monte_neo.deploy import journal as jr
from monte_neo.disclaimer import html_footer
from monte_neo.verify.report_html import CSP

DEFAULT_STRESS = {"COVID crash": ("2020-02-10", "2020-04-30"), "Terra/Luna collapse": ("2022-04-25", "2022-07-15"),
                  "FTX collapse": ("2022-10-31", "2022-12-31")}
LIMITATIONS = [
    "Demo (testnet) execution: thin order books and periodic resets. P&L is measured at mainnet prices with the cost model of the start entry; demo fills prove the process, not the slippage of a real account.",
    "A short forward record says little by itself; the Monte-Neo verdict states its significance for the number of trials priced.",
    "Stress replays are backtests of the frozen strategy, not recorded results; past performance does not predict future returns.",
    "Single venue (Binance); venue risk is not diversified.",
    "Not investment advice.",
]


def parse_window(text: str) -> tuple[str, tuple[str, str]]:
    """``NAME=YYYY-MM-DD:YYYY-MM-DD`` -> ``(NAME, (start, end))``."""
    try:
        name, span = text.split("=", 1)
        a, b = span.split(":", 1)
        da, db = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    except ValueError as exc:
        raise ValueError(f"bad stress window {text!r}: use NAME=YYYY-MM-DD:YYYY-MM-DD") from exc
    if not name.strip() or da >= db:
        raise ValueError(f"bad stress window {text!r}: need a name and start < end")
    return name.strip(), (a, b)


# ---------------------------------------------------------------- statistics (stdlib)
def _ols(y: list[float], x: list[float]) -> dict[str, float | None]:
    n = min(len(y), len(x))
    if n < 10:
        return {"beta": None, "alpha_annual": None, "alpha_t": None, "r2": None}
    y, x = y[-n:], x[-n:]
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    beta = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / sxx if sxx else 0.0
    alpha = my - beta * mx
    res = [b - alpha - beta * a for a, b in zip(x, y, strict=True)]
    s2 = sum(r * r for r in res) / (n - 2)
    se_a = math.sqrt(s2 * (1.0 / n + mx * mx / sxx)) if sxx else None
    syy = sum((b - my) ** 2 for b in y)
    return {"beta": beta, "alpha_annual": alpha * 365, "alpha_t": alpha / se_a if se_a else None, "r2": 1 - sum(r * r for r in res) / syy if syy else None}


def _annual_vol(r: list[float]) -> float | None:
    if len(r) < 2:
        return None
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1) * 365)


def _dd_duration(navs: list[float], days: list[str]) -> dict[str, Any]:
    peak, peak_i, worst, start, end, longest = -math.inf, 0, 0.0, None, None, 0
    for i, v in enumerate(navs):
        if v >= peak:
            peak, peak_i = v, i
        dd = v / peak - 1.0
        if dd < worst:
            worst, start, end = dd, days[peak_i], days[i]
        longest = max(longest, i - peak_i)
    return {"max_drawdown": worst, "peak_day": start, "trough_day": end, "longest_underwater_days": longest}


def _period_returns(marks: list[dict[str, Any]], key: int) -> list[tuple[str, float]]:
    """Returns per calendar period (key 7 = month YYYY-MM): from the last mark of the previous period to the last of this one."""
    out: list[tuple[str, float]] = []
    prev_nav = marks[0]["nav"] if marks else None
    prev_key, last = None, None
    for m in marks:
        k = m["day"][:key]
        if prev_key is not None and k != prev_key:
            out.append((prev_key, last / prev_nav - 1.0))  # type: ignore[operator]
            prev_nav = last
        prev_key, last = k, m["nav"]
    if prev_key is not None:
        out.append((prev_key + " (to date)", last / prev_nav - 1.0))  # type: ignore[operator]
    return out


# ---------------------------------------------------------------- backtest replay of the frozen strategy
def _history(symbol: str, start: str, end: str, lookback: int, venue: str = "binance_spot") -> list[tuple[str, float]]:
    """Mainnet daily closes (of the run's venue) from ``lookback`` + 35 days before ``start`` to ``end``."""
    from monte_neo.deploy import connectors

    klines = connectors.klines_fn(connectors.venue(venue))
    s = dt.date.fromisoformat(start) - dt.timedelta(days=lookback + 35)
    e = dt.date.fromisoformat(end)
    out: dict[str, float] = {}
    cursor = e
    while cursor > s:
        end_ms = int(dt.datetime(cursor.year, cursor.month, cursor.day, tzinfo=dt.UTC).timestamp() * 1000) + 86_399_999
        rows = klines(symbol, limit=1000, end_ms=end_ms)
        if not rows:
            break
        for ms, c in rows:
            out[dt.datetime.fromtimestamp(ms / 1000, dt.UTC).date().isoformat()] = c
        first = dt.datetime.fromtimestamp(rows[0][0] / 1000, dt.UTC).date()
        if first >= cursor:
            break
        cursor = first - dt.timedelta(days=1)
    return sorted((d, c) for d, c in out.items() if s.isoformat() <= d <= end)


def replay(cfg: dict[str, Any], fn: plugin.WeightsFn, start: str, end: str) -> dict[str, Any]:
    """Run the frozen strategy on [start, end]: rebalance on the run's schedule with closes up to the previous day and the run's costs.

    On a perpetual-futures venue the replay leaves funding out (the stress windows predate most funding history); the
    forward books charge it.
    """
    from monte_neo.deploy import connectors

    v = connectors.venue(cfg)
    symbols, lookback, capital = cfg["symbols"], int(cfg.get("lookback", runner.LOOKBACK)), float(cfg["capital"])
    hist = {s: dict(_history(s, start, end, lookback, v.id)) for s in symbols}
    days = sorted(set.intersection(*(set(h) for h in hist.values()))) if hist else []
    if not any(d >= start for d in days):
        return {"start": start, "end": end, "error": "no common history for all symbols in this window"}
    cash, pos = capital, {s: 0.0 for s in symbols}
    cost = (cfg["cost_model"]["fee_bps"] + cfg["cost_model"]["slippage_bps"]) / 1e4
    navs: list[tuple[str, float]] = []
    try:
        for i, d in enumerate(days):
            if d < start or i == 0:
                continue
            px_prev = {s: hist[s][days[i - 1]] for s in symbols}
            nav_prev = cash + sum(pos[s] * px_prev[s] for s in symbols)
            if runner.is_rebalance_day(cfg, dt.date.fromisoformat(d)):
                closes = {s: [hist[s][x] for x in days[:i]][-lookback:] for s in symbols}
                w = plugin.call(fn, closes, symbols, allow_short=v.short, max_gross=float(cfg.get("max_gross", 1.0)))
                for s in symbols:
                    delta = w[s] * nav_prev / px_prev[s] - pos[s]
                    cash -= delta * px_prev[s] + abs(delta) * px_prev[s] * cost
                    pos[s] += delta
            navs.append((d, cash + sum(pos[s] * hist[s][d] for s in symbols)))
    except plugin.PluginError as exc:
        return {"start": start, "end": end, "error": str(exc)}
    vals = [v for _, v in navs]
    rets = [b / a - 1.0 for a, b in zip(vals, vals[1:], strict=False)]
    bench = [sum(hist[s][b] / hist[s][a] - 1.0 for s in symbols) / len(symbols) for (a, _), (b, _) in zip(navs, navs[1:], strict=False)]
    return {"start": start, "end": end, "days": len(navs), "return": vals[-1] / vals[0] - 1.0 if len(vals) > 1 else None,
            "max_drawdown": metrics.max_drawdown(vals) if vals else None, "sharpe": metrics.sharpe(rets),
            "benchmark_return": math.prod(1 + r for r in bench) - 1.0 if bench else None,
            "benchmark_max_drawdown": metrics.max_drawdown([math.prod(1 + r for r in bench[:k]) for k in range(len(bench) + 1)]) if bench else None}


# ---------------------------------------------------------------- the numbers and the page
def numbers(journal_path: Path, windows: dict[str, tuple[str, str]] | None = None, strategy_path: Path | None = None) -> dict[str, Any]:
    """Every number of the report. ``windows`` (name -> (start, end)) switches the stress replays on."""
    entries = list(jr.Journal(journal_path).entries())
    start = next((e["body"] for e in entries if e["kind"] == "start"), {})
    marks = account.replay(entries, "paper")["marks"]
    navs, days = [m["nav"] for m in marks], [m["day"] for m in marks]
    r = account.daily_returns(marks)
    bench = []
    for a, b in zip(marks, marks[1:], strict=False):
        common = [s for s in a["prices"] if s in b["prices"]]
        bench.append(sum(b["prices"][s] / a["prices"][s] - 1.0 for s in common) / len(common) if common else 0.0)
    months = _period_returns(marks, 7)
    certs = [e["body"] for e in entries if e["kind"] == "certify"]
    anchors = [e["body"] for e in entries if e["kind"] == "anchor" and "skipped" not in e["body"]]
    chain = jr.verify(journal_path)
    out: dict[str, Any] = {
        "run": {k: start.get(k) for k in ("mode", "rebalance", "weekday", "first_day", "capital", "symbols", "cost_model", "kill_drawdown", "strategy", "certificate", "warnings")},
        "journal": {"ok": chain["ok"], "entries": chain["entries"], "head": chain["head"], "last_anchor": anchors[-1] if anchors else None, "anchors": len(anchors)},
        "summary": metrics.summary(entries),
        "risk": {**_dd_duration(navs, days), "annual_vol": _annual_vol(r), "worst_day": min(r) if r else None, "best_day": max(r) if r else None,
                 "worst_month": min((v for _, v in months), default=None), **{f"var_es_{q}": metrics.var_es(r, q / 100) for q in (95, 99)}},
        "attribution": _ols(r, bench),
        "months": months,
        "certificate": certs[-1] if certs else None,
        "operations": {k: sum(1 for e in entries if e["kind"] == k) for k in ("deviation", "repair", "kill", "skip", "order", "fill")},
        "late_days": sum(1 for e in entries if e["kind"] == "mark" and e["body"].get("late")),
        "deviations": [e["body"] for e in entries if e["kind"] == "deviation"],
    }
    if windows:
        fn = plugin.load(strategy_path or journal_path.parent / "strategy.py")
        out["stress"] = {name: replay(start, fn, a, b) for name, (a, b) in windows.items()}
    return out


def _p(x: float | None, d: int = 2) -> str:
    return "n/a" if x is None else f"{x * 100:.{d}f} %"


def _f(x: float | None, d: int = 2) -> str:
    return "n/a" if x is None else f"{x:,.{d}f}"


def _e(x: Any) -> str:
    return html.escape(str(x))


def render(n: dict[str, Any]) -> str:
    s, rk, at, j, run = n["summary"], n["risk"], n["attribution"], n["journal"], n["run"]
    foot = f"Journal head {j['head'][:16]}... ({j['entries']} entries, chain {'intact' if j['ok'] else 'BROKEN'}); last RFC 3161 anchor: {_e((j['last_anchor'] or {}).get('day', 'none'))}"
    months = "".join(f"<tr><td>{_e(k)}</td><td>{_p(v)}</td></tr>" for k, v in n["months"]) or "<tr><td colspan=2>no full period yet</td></tr>"
    stress_rows = []
    for k, v in n.get("stress", {}).items():
        if "error" in v:
            stress_rows.append(f"<tr><td>{_e(k)}</td><td>{_e(v['start'])} - {_e(v['end'])}</td><td colspan=5>{_e(v['error'])}</td></tr>")
        else:
            stress_rows.append(f"<tr><td>{_e(k)}</td><td>{v['start']} - {v['end']}</td><td>{_p(v['return'])}</td><td>{_p(v['max_drawdown'])}</td><td>{_f(v['sharpe'])}</td><td>{_p(v['benchmark_return'])}</td><td>{_p(v['benchmark_max_drawdown'])}</td></tr>")
    stress = "".join(stress_rows) or "<tr><td colspan=7>not run</td></tr>"
    cert = n["certificate"]
    cert_html = (f"<p>Verdict <b>{_e(cert['verdict'])}</b>, certificate <code>{_e(cert['certificate_id'])}</code>, "
                 f"{cert['days']} days, trials priced: {cert['n_strategies']}, engine {_e(cert['engine_version'])}.</p>"
                 + "".join(f"<p class=m>{_e(x)}</p>" for x in cert.get("reasons", []))) if cert else "<p class=m>Not certified yet: run <code>monte-neo deploy certify</code>.</p>"
    lim = "".join(f"<li>{_e(x)}</li>" for x in LIMITATIONS)
    ops = n["operations"]
    el = run.get("certificate") or {}
    warn = "".join(f"<li>{_e(w)}</li>" for w in (run.get("warnings") or [])) or "<li>none</li>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="{CSP}"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Forward record evidence report</title><style>
body{{font:13px/1.5 Georgia,serif;color:#141922;max-width:900px;margin:24px auto;padding:0 16px}}h1{{font-size:22px}}h2{{font-size:16px;border-bottom:1px solid #ccd;padding-bottom:3px;margin-top:22px}}
table{{border-collapse:collapse;width:100%;font:12px Helvetica,Arial,sans-serif}}td,th{{border-bottom:1px solid #e3e6ea;padding:4px 6px;text-align:left}}.m{{color:#5b6573}}code{{font-size:11px}}
footer{{margin-top:24px;font:11px Helvetica,Arial,sans-serif;color:#5b6573;border-top:1px solid #ccd;padding-top:6px}}@media print{{body{{margin:0}}h2{{break-after:avoid}}}}
</style></head><body>
<h1>Forward record: evidence report</h1>
<p class=m>Strategy SHA-256 <code>{_e((run.get('strategy') or {}).get('sha256'))}</code> · first day {_e(run['first_day'])} · execution {_e(run['mode'])} (demo, not live capital) · rebalance {_e(run['rebalance'])} · every number is reproducible with <code>monte-neo deploy report --verify</code>.</p>
<h2>1. Summary</h2><table>
<tr><td>Days recorded</td><td>{s['days']} ({s['weeks']:.1f} weeks)</td><td>Net return</td><td>{_p(s['paper_return'])}</td></tr>
<tr><td>Sharpe (net)</td><td>{_f(s['sharpe'])}</td><td>Sharpe (2x costs)</td><td>{_f(s['sharpe_costs_x2'])}</td></tr>
<tr><td>Max drawdown</td><td>{_p(rk['max_drawdown'])}</td><td>Longest underwater</td><td>{rk['longest_underwater_days']} days</td></tr>
<tr><td>Annual volatility</td><td>{_p(rk['annual_vol'])}</td><td>Tracking error demo vs paper</td><td>{_p(s['tracking_error'])} a year</td></tr></table>
<h2>2. Eligibility at start</h2><p class=m>Certificate <code>{_e(el.get('id'))}</code>, verdict {_e(el.get('verdict'))}, ARL {_e(el.get('arl'))}, trials {_e(el.get('n_trials'))}.</p><ul>{warn}</ul>
<h2>3. Net returns by month (recorded period only)</h2><table><tr><th>Month</th><th>Net return</th></tr>{months}</table>
<h2>4. Risk</h2><table>
<tr><td>Worst / best day</td><td>{_p(rk['worst_day'])} / {_p(rk['best_day'])}</td><td>Worst week</td><td>{_p(s['worst_week'])}</td></tr>
<tr><td>One-day VaR / ES 95</td><td>{_p(rk['var_es_95']['var'])} / {_p(rk['var_es_95']['es'])}</td><td>One-day VaR / ES 99</td><td>{_p(rk['var_es_99']['var'])} / {_p(rk['var_es_99']['es'])}</td></tr>
<tr><td>Drawdown peak to trough</td><td>{_e(rk['peak_day'])} to {_e(rk['trough_day'])}</td><td>Kill switch</td><td>{_p(run['kill_drawdown'])} from peak ({'triggered' if ops['kill'] else 'not triggered'})</td></tr></table>
<h2>5. Attribution against buy and hold of the same symbols</h2><table><tr><td>Beta</td><td>{_f(at['beta'])}</td><td>Alpha (annual)</td><td>{_p(at['alpha_annual'])}</td><td>Alpha t (OLS)</td><td>{_f(at['alpha_t'])}</td><td>R2</td><td>{_f(at['r2'])}</td></tr></table>
<h2>6. Monte-Neo certificate of the forward returns</h2>{cert_html}
<h2>7. Stress replays (backtests of the frozen strategy, not recorded results)</h2>
<table><tr><th>Window</th><th>Dates</th><th>Return</th><th>Max DD</th><th>Sharpe</th><th>Buy &amp; hold</th><th>B&amp;H max DD</th></tr>{stress}</table>
<h2>8. Operations</h2><table><tr><td>Orders / fills</td><td>{ops['order']} / {ops['fill']}</td><td>Days recorded late</td><td>{n['late_days']}</td></tr>
<tr><td>Deviations from protocol</td><td>{ops['deviation']}</td><td>Repairs of an interrupted write</td><td>{ops['repair']}</td></tr>
<tr><td>Orders skipped (below exchange minimum)</td><td>{ops['skip']}</td><td>RFC 3161 anchors</td><td>{j['anchors']}</td></tr></table>
<p class=m>Cost model {_e(json.dumps(run['cost_model']))} per side.</p>
<h2>9. Limitations</h2><ol>{lim}</ol>
<footer>{_e(foot)}.</footer>{html_footer()}</body></html>"""


def _digest(n: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(n, sort_keys=True, default=str).encode()).hexdigest()


def _norm(n: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(n, default=str))  # type: ignore[no-any-return]


def build(journal_path: Path, out: Path, windows: dict[str, tuple[str, str]] | None = None, strategy_path: Path | None = None) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    n = _norm(numbers(journal_path, windows, strategy_path))
    (out / "report.html").write_text(render(n), encoding="utf-8")
    manifest = {"numbers": n, "sha256": _digest(n), "journal_head": n["journal"]["head"]}
    (out / "report_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    return {"report": str(out / "report.html"), "sha256": manifest["sha256"]}


def verify(journal_path: Path, out: Path, strategy_path: Path | None = None) -> dict[str, Any]:
    """Recompute every number from the journal (and public bars) and compare with the saved manifest."""
    manifest_path = out / "report_manifest.json"
    if not manifest_path.exists():
        return {"ok": False, "differs": ["report_manifest.json is missing: run report first"]}
    saved = json.loads(manifest_path.read_text())
    windows = {k: (v["start"], v["end"]) for k, v in saved["numbers"].get("stress", {}).items()} or None
    fresh = _norm(numbers(journal_path, windows, strategy_path))
    diffs = [k for k in sorted(set(saved["numbers"]) | set(fresh))
             if json.dumps(saved["numbers"].get(k), sort_keys=True) != json.dumps(fresh.get(k), sort_keys=True)]
    if _digest(saved["numbers"]) != saved["sha256"]:
        diffs.append("manifest sha256 does not match its own numbers (manifest edited)")
    return {"ok": not diffs, "differs": diffs, "saved_sha256": saved["sha256"], "fresh_sha256": _digest(fresh)}
