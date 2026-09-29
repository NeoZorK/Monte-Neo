"""SVG charts for the HTML report: inline, no scripts, no external resources.

The input is a certificate, so it is treated as untrusted: every number is checked to be
finite before it is drawn, lists are capped, and every piece of text is escaped.
"""

from __future__ import annotations

import html
import math
from typing import Any

W, H, PAD = 960, 240, 40
SMALL_W = 520  # half-width figures: text keeps a readable size when two sit side by side
MAX_POINTS = 1000
MAX_CELLS = 400


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _f(value: Any) -> float | None:
    """A finite float, or None (booleans and text are not numbers here)."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return float(value)


def _floats(values: Any, limit: int = MAX_POINTS) -> list[float]:
    if not isinstance(values, list):
        return []
    return [x for x in (_f(v) for v in values[:limit]) if x is not None]


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _svg(body: str, label: str, height: int = H, width: int = W) -> str:
    return f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{_e(label)}">{body}</svg>'


def _line(values: list[float], lo: float, hi: float, height: int = H, pad: int = PAD, width: int = W) -> str:
    span = (hi - lo) or 1.0
    n = max(len(values) - 1, 1)
    return " ".join(
        f"{pad + (width - 2 * pad) * i / n:.1f},{height - pad - (height - 2 * pad) * (v - lo) / span:.1f}"
        for i, v in enumerate(values)
    )


def _y(v: float, lo: float, hi: float, height: int = H, pad: int = PAD) -> float:
    return height - pad - (height - 2 * pad) * (v - lo) / ((hi - lo) or 1.0)


def equity_chart(series: dict[str, Any]) -> str:
    """Strategy and buy-and-hold on a log scale (linear when a value is not positive), then the drawdown."""
    series = _dict(series)
    equity, bench = _floats(series.get("equity")), _floats(series.get("benchmark"))
    if len(equity) < 2:
        return '<p class="muted">No equity series in this certificate.</p>'
    both = equity + bench
    log = min(both) > 0
    tf = math.log if log else float
    eq, bh = [tf(v) for v in equity], [tf(v) for v in bench]
    lo, hi = min(eq + bh), max(eq + bh)
    times = series.get("time") if isinstance(series.get("time"), list) else []
    bars = series.get("bar") if isinstance(series.get("bar"), list) else []
    first = str(times[0])[:10] if times else f"bar {bars[0] if bars else 0}"
    last = str(times[-1])[:10] if times else f"bar {bars[-1] if bars else len(equity) - 1}"
    ticks = "".join(
        f'<line x1="{PAD}" x2="{W - PAD}" y1="{_y(t, lo, hi):.1f}" y2="{_y(t, lo, hi):.1f}" stroke="var(--line)"/>'
        f'<text x="4" y="{_y(t, lo, hi) + 4:.1f}">{(math.exp(t) if log else t):.2f}×</text>'
        for t in (lo, (lo + hi) / 2, hi)
    )
    top = (
        f"{ticks}"
        f'<polyline fill="none" stroke="var(--bench)" stroke-width="1.5" points="{_line(bh, lo, hi)}"/>'
        f'<polyline fill="none" stroke="var(--strat)" stroke-width="2" points="{_line(eq, lo, hi)}"/>'
        f'<text x="{PAD}" y="{H - 10}">{_e(first)}</text><text x="{W - PAD}" y="{H - 10}" text-anchor="end">{_e(last)}</text>'
    )
    peak, drawdown = equity[0], []
    for v in equity:
        peak = max(peak, v)
        drawdown.append(v / peak - 1.0 if peak > 0 else 0.0)
    dd_lo = min(drawdown) or -1e-9
    dd_h = 100
    area = f"{PAD},{_y(0.0, dd_lo, 0.0, dd_h, 14):.1f} {_line(drawdown, dd_lo, 0.0, dd_h, 14)} {W - PAD},{_y(0.0, dd_lo, 0.0, dd_h, 14):.1f}"
    under = (
        f'<polygon fill="var(--bad)" fill-opacity="0.18" points="{area}"/>'
        f'<polyline fill="none" stroke="var(--bad)" stroke-width="1.5" points="{_line(drawdown, dd_lo, 0.0, dd_h, 14)}"/>'
        f'<text x="4" y="18">0%</text><text x="4" y="{dd_h - 4}">{dd_lo:.1%}</text>'
    )
    legend = (
        '<div class="legend muted"><span><i class="sw" style="background:var(--strat)"></i>strategy</span>'
        '<span><i class="sw" style="background:var(--bench)"></i>buy &amp; hold</span>'
        f'<span><i class="sw" style="background:var(--bad)"></i>drawdown</span>{"<span>log scale</span>" if log else ""}</div>'
    )
    return _svg(top, "Equity: strategy and buy and hold") + _svg(under, "Drawdown", dd_h) + legend


def rolling_sharpe_chart(block: dict[str, Any]) -> str:
    block = _dict(block)
    values = _floats(block.get("values"))
    if len(values) < 2:
        return ""
    lo, hi = min(min(values), 0.0), max(max(values), 0.0)
    height, w = 170, SMALL_W
    zero = _y(0.0, lo, hi, height)
    body = (
        f'<line x1="{PAD}" x2="{w - PAD}" y1="{zero:.1f}" y2="{zero:.1f}" stroke="var(--line)" stroke-dasharray="4 4"/>'
        f'<polyline fill="none" stroke="var(--strat)" stroke-width="1.8" points="{_line(values, lo, hi, height, PAD, w)}"/>'
        f'<text x="4" y="{_y(hi, lo, hi, height) + 4:.1f}">{hi:.1f}</text><text x="4" y="{_y(lo, lo, hi, height) + 4:.1f}">{lo:.1f}</text>'
    )
    return _svg(body, "Rolling Sharpe", height, w)


def monthly_heatmap(monthly: Any) -> str:
    """Return per calendar month: one row per year, green for gains and red for losses."""
    cells: dict[tuple[int, int], float] = {}
    for row in (monthly if isinstance(monthly, list) else [])[:MAX_CELLS]:
        if isinstance(row, list) and len(row) == 3 and all(_f(x) is not None for x in row):
            year, month, ret = int(row[0]), int(row[1]), float(row[2])
            if 1 <= month <= 12 and 1000 <= year <= 3000:
                cells[(year, month)] = ret
    if not cells:
        return ""
    years = sorted({y for y, _ in cells})
    scale = max(0.01, max(abs(v) for v in cells.values()))
    cw, ch, left, top = 66, 26, 52, 22
    body = "".join(f'<text x="{left + (m - 1) * cw + cw / 2}" y="14" text-anchor="middle">{name}</text>'
                   for m, name in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1))
    for r, year in enumerate(years):
        body += f'<text x="4" y="{top + r * ch + 17}">{year}</text>'
        for m in range(1, 13):
            ret = cells.get((year, m))
            if ret is None:
                continue
            tone = "var(--good)" if ret >= 0 else "var(--bad)"
            body += (
                f'<rect x="{left + (m - 1) * cw + 1}" y="{top + r * ch + 1}" width="{cw - 2}" height="{ch - 2}" rx="4" '
                f'fill="{tone}" fill-opacity="{0.12 + 0.75 * min(abs(ret) / scale, 1.0):.2f}"/>'
                f'<text class="cell" x="{left + (m - 1) * cw + cw / 2}" y="{top + r * ch + 17}" text-anchor="middle">{ret:+.1%}</text>'
            )
    return _svg(body, "Monthly returns", top + len(years) * ch + 6).replace(f'viewBox="0 0 {W} ', f'viewBox="0 0 {left + 12 * cw} ', 1)


def _bars(counts: list[int], edges: list[float], marks: list[tuple[float, str, str]], label: str, xfmt: str) -> str:
    height, pad, w = 200, 30, SMALL_W
    top = max(counts) or 1
    lo, hi = edges[0], edges[-1]
    span = (hi - lo) or 1.0
    bw = (w - 2 * pad) / len(counts)
    body = "".join(
        f'<rect x="{pad + i * bw + 1:.1f}" y="{height - pad - (height - 2 * pad) * c / top:.1f}" width="{bw - 2:.1f}" '
        f'height="{(height - 2 * pad) * c / top:.1f}" fill="var(--strat)" fill-opacity="0.55"/>'
        for i, c in enumerate(counts)
    )
    for value, tone, text in marks:
        x = pad + (w - 2 * pad) * min(max((value - lo) / span, 0.0), 1.0)
        body += f'<line x1="{x:.1f}" x2="{x:.1f}" y1="12" y2="{height - pad}" stroke="var({tone})" stroke-width="2"/>'
        right = x > w * 0.55
        anchor = ' text-anchor="end"' if right else ""
        body += f'<text x="{x + (-4 if right else 4):.1f}" y="24"{anchor}>{_e(text)}</text>'
    body += f'<text x="{pad}" y="{height - 8}">{xfmt.format(lo)}</text><text x="{w - pad}" y="{height - 8}" text-anchor="end">{xfmt.format(hi)}</text>'
    return _svg(body, label, height, w)


def returns_histogram_chart(block: dict[str, Any]) -> str:
    block = _dict(block)
    edges, counts = _floats(block.get("edges")), [int(c) for c in _floats(block.get("counts"))]
    if len(counts) < 2 or len(edges) != len(counts) + 1:
        return ""
    mean = _f(block.get("mean"))
    marks = [(mean, "--good" if mean >= 0 else "--bad", f"mean {mean:+.3%}")] if mean is not None else []
    return _bars(counts, edges, marks, "Distribution of per-bar returns", "{:+.2%}")


def timing_chart(block: dict[str, Any]) -> str:
    """Net return of the shifted copies of the positions, with the real return marked."""
    block = _dict(block)
    shifted, actual = _floats(block.get("shifted")), _f(block.get("actual"))
    if len(shifted) < 10 or actual is None:
        return ""
    lo, hi = min(shifted + [actual]), max(shifted + [actual])
    if hi <= lo:
        return ""
    bins = 24
    step = (hi - lo) / bins
    counts = [0] * bins
    for v in shifted:
        counts[min(int((v - lo) / step), bins - 1)] += 1
    edges = [lo + i * step for i in range(bins + 1)]
    p = _f(block.get("p_value"))
    text = f"actual {actual:+.1%}" + (f" (p {p:.3f})" if p is not None else "")
    return _bars(counts, edges, [(actual, "--good" if p is not None and p <= 0.05 else "--bad", text)], "Shifted copies against the real return", "{:+.0%}")


def cost_chart(block: dict[str, Any]) -> str:
    block = _dict(block)
    raw = block.get("points") if isinstance(block.get("points"), list) else []
    points = [(_f(p.get("bps")), _f(p.get("return"))) for p in raw[:50] if isinstance(p, dict)]
    points = [(x, y) for x, y in points if x is not None and y is not None]
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
        f'<text x="{pad}" y="{height - 8}">{xs[0]:g} bps</text><text x="{w - pad}" y="{height - 8}" text-anchor="end">{xs[-1]:g} bps per side</text>'
    )
    modeled = _f(block.get("modeled_bps"))
    if modeled is not None and xs[0] <= modeled <= xs[-1]:
        x = sx(modeled)
        body += f'<line x1="{x:.1f}" x2="{x:.1f}" y1="12" y2="{height - pad}" stroke="var(--warn)" stroke-width="2"/><text x="{x + 4:.1f}" y="24">modeled {modeled:g} bps</text>'
    return _svg(body, "Net return against trading costs", height, w)


def grid_heatmap(grid: dict[str, Any]) -> str:
    """Sharpe of every parameter combination (first two parameters); a plateau or a peak shows at a glance."""
    grid = _dict(grid)
    spec = _dict(grid.get("spec"))
    sharpes = _floats(grid.get("combo_sharpes"), 5000)
    names = list(spec)[:2]
    if len(names) < 1 or not sharpes:
        return ""
    axes = [list(spec[n])[:40] if isinstance(spec[n], list) else [] for n in names]
    if not all(axes) or math.prod(len(a) for a in list(spec.values()) if isinstance(a, list)) != len(sharpes):
        return ""
    rows, cols = (axes[0], axes[1]) if len(names) == 2 else (axes[0], [""])
    inner = len(sharpes) // (len(rows) * len(cols))  # remaining parameters: show the best value of each cell
    best = {}
    for i, s in enumerate(sharpes):
        cell = i // inner
        best[cell] = max(best.get(cell, -math.inf), s)
    top = max(max(best.values()), 1e-12)
    cw, ch, left, head = 70, 26, 90, 26
    body = "".join(f'<text x="{left + j * cw + cw / 2}" y="16" text-anchor="middle">{_e(c)}</text>' for j, c in enumerate(cols))
    for i, r in enumerate(rows):
        body += f'<text x="4" y="{head + i * ch + 17}">{_e(r)}</text>'
        for j in range(len(cols)):
            value = best[i * len(cols) + j]
            tone = "var(--good)" if value >= 0 else "var(--bad)"
            body += (
                f'<rect x="{left + j * cw + 1}" y="{head + i * ch + 1}" width="{cw - 2}" height="{ch - 2}" rx="4" fill="{tone}" '
                f'fill-opacity="{0.1 + 0.8 * min(abs(value) / top, 1.0):.2f}"/>'
                f'<text class="cell" x="{left + j * cw + cw / 2}" y="{head + i * ch + 17}" text-anchor="middle">{value:.3f}</text>'
            )
    title = f"Sharpe per bar: rows {_e(names[0])}" + (f", columns {_e(names[1])}" if len(names) == 2 else "")
    svg = _svg(body, title, head + len(rows) * ch + 6).replace(f'viewBox="0 0 {W} ', f'viewBox="0 0 {left + len(cols) * cw} ', 1)
    return f'<p class="muted">{title}</p>{svg}'


__all__ = ["cost_chart", "equity_chart", "grid_heatmap", "monthly_heatmap", "returns_histogram_chart", "rolling_sharpe_chart", "timing_chart"]
