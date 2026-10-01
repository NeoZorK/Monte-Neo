"""Latency section of the HTML report for quote certificates (``verify_quotes``): numbers and one chart."""

from __future__ import annotations

import math
from typing import Any

from monte_neo.verify.report_charts import SMALL_W, _dict, _e, _f, _svg, _y


def _pct(value: Any) -> str:
    return "—" if _f(value) is None else f"{float(value):+.2%}"


def _ms(value: Any) -> str:
    return "—" if _f(value) is None else f"{float(value):.0f} ms"


def _stat(label: str, value: str) -> str:
    return f'<div class="stat"><span class="muted">{_e(label)}</span><b>{_e(value)}</b></div>'


def _to_float(text: Any) -> Any:
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def latency_chart(scan: Any) -> str:
    """Net return against extra data delay in ms (dashed zero line, marker at the observed p95)."""
    block = _dict(scan)
    raw = _dict(block.get("return_by_extra_ms"))
    points = sorted((x, y) for x, y in ((_f(_to_float(k)), _f(v)) for k, v in list(raw.items())[:50]) if x is not None and y is not None)
    if len(points) < 2:
        return ""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    lo, hi = min(min(ys), 0.0), max(max(ys), 0.0)
    height, pad, w = 200, 34, SMALL_W
    sx = lambda x: pad + (w - 2 * pad) * (x - xs[0]) / ((xs[-1] - xs[0]) or 1.0)  # noqa: E731
    line = " ".join(f"{sx(x):.1f},{_y(y, lo, hi, height, pad):.1f}" for x, y in points)
    zero = _y(0.0, lo, hi, height, pad)
    body = (
        f'<line x1="{pad}" x2="{w - pad}" y1="{zero:.1f}" y2="{zero:.1f}" stroke="var(--line)" stroke-dasharray="4 4"/>'
        f'<polyline fill="none" stroke="var(--strat)" stroke-width="2" points="{line}"/>'
        f'<text x="4" y="{_y(hi, lo, hi, height, pad) + 4:.1f}">{hi:+.0%}</text><text x="4" y="{_y(lo, lo, hi, height, pad) + 4:.1f}">{lo:+.0%}</text>'
        f'<text x="{pad}" y="{height - 8}">{xs[0]:g} ms</text><text x="{w - pad}" y="{height - 8}" text-anchor="end">{xs[-1]:g} ms extra delay</text>'
    )
    p95 = _f(block.get("p95_latency_ms"))
    if p95 is not None and xs[0] <= p95 <= xs[-1]:
        x = sx(p95)
        body += f'<line x1="{x:.1f}" x2="{x:.1f}" y1="12" y2="{height - pad}" stroke="var(--warn)" stroke-width="2"/><text x="{x + 4:.1f}" y="24">observed p95 {p95:g} ms</text>'
    return _svg(body, "Net return against extra data delay", height, w)


def latency_section(report: dict[str, Any]) -> str:
    """Empty for ordinary certificates; for a quote certificate the latency numbers and chart."""
    block = report.get("latency")
    if not isinstance(block, dict):
        return ""
    arrival, scan, mc, quality = (_dict(block.get(k)) for k in ("arrival", "scan", "monte_carlo", "quality"))
    lat = _dict(quality.get("latency_ms"))
    stats = "".join(
        [
            _stat("return, exchange clock", _pct(arrival.get("return_exchange_clock"))),
            _stat("return, arrival clock", _pct(arrival.get("return_arrival_clock"))),
            _stat("latency p50 / p95", f"{_ms(lat.get('p50'))} / {_ms(lat.get('p95'))}"),
            _stat("profit vanishes at", "—" if scan.get("profit_vanishes_at_extra_ms") is None else f"+{_ms(scan.get('profit_vanishes_at_extra_ms'))}"),
            _stat("latency draws that lose", "—" if _f(mc.get("probability_of_loss")) is None else f"{float(mc['probability_of_loss']):.0%}"),
            _stat("return p5 / median / p95", " / ".join(_pct(mc.get(k)) for k in ("return_p5", "return_p50", "return_p95"))),
        ]
    )
    chart = latency_chart(scan)
    spread = _dict(block.get("spread"))
    if _f(spread.get("median_bps")) is not None:
        stats += _stat("half-spread (median / p95)", f"{float(spread['median_bps']):.2f} / {float(spread.get('p95_bps') or 0):.2f} bps")
    notes = report.get("assumptions")
    assumed = (
        "<div class='card'><b>What this run assumes</b><ul>" + "".join(f"<li>{_e(x)}</li>" for x in notes[:12]) + "</ul></div>"
        if isinstance(notes, list) and notes
        else ""
    )
    return (
        "<h2>Time and latency</h2>"
        f"<div class='card grid'>{stats}</div>"
        + (f"<div class='card'><b>Net return against extra data delay</b>{chart}"
           "<p class='muted'>Positions come from bars binned by arrival time plus the extra delay and are filled on the market bars.</p></div>" if chart else "")
        + assumed
    )


__all__ = ["latency_chart", "latency_section"]
