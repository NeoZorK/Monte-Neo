"""Repaint probes: does a signal change after it was shown?

Two different questions:

* **History** (``probe_repaint_history``): the signal of a closed bar must stay the same when more bars arrive.
  It is checked on prefixes that follow one another (the table as it grew), on the table extended by synthetic
  bars, and on a small revision of the last bars. A signal that moves is a ZigZag-like or confirmed-later one:
  the backtest shows a signal that nobody could have seen.
* **The forming bar** (``probe_repaint_live``): the bar's high, low, close and volume are replaced by their state
  at 0 / 25 / 50 / 75 % of the bar. A signal that cannot change in any of these states is *known at the open*.
  A signal that does change is *decided at the close*: that is how every close-based rule works, and it is not a
  fault, but it must be acted on only after the bar closed. A strategy that declares ``signal_timing="open"``
  and flickers fails.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.executor import Head
from monte_neo.verify.lookahead import MAX_REPORTED, _checkpoints, _decision_points, run_positions

MODES = ("off", "auto", "strict")
TIMINGS = ("close", "open")
FRACTIONS = (0.0, 0.25, 0.5, 0.75)
REVISED_BARS = 3
EXTENSION_SEED = 20_261_005


def _extend(df: pd.DataFrame, k: int) -> pd.DataFrame:
    """The table followed by ``k`` synthetic bars with the volatility of its last bars (stamps continue)."""
    rng = np.random.default_rng(EXTENSION_SEED)
    close = df["close"].to_numpy(dtype=np.float64)
    vol = float(np.nanstd(np.diff(np.log(close[-256:])))) or 1e-3
    steps = rng.normal(0.0, vol, size=k)
    closes = close[-1] * np.exp(np.cumsum(steps))
    opens = np.concatenate([[close[-1]], closes[:-1]])
    spread = np.abs(rng.normal(0.0, vol, size=k)) * closes
    new = {
        "open": opens, "close": closes,
        "high": np.maximum(opens, closes) + spread, "low": np.maximum(np.minimum(opens, closes) - spread, 1e-9),
    }
    tail = pd.DataFrame({c: new[c] for c in new}, index=range(len(df), len(df) + k))
    for col in df.columns:
        if col in new:
            continue
        if col == "timestamp":
            stamps = pd.to_datetime(df[col], errors="coerce")
            step = stamps.diff().median() if len(stamps) > 1 else pd.Timedelta(days=1)
            if pd.isna(step):
                tail[col] = df[col].iloc[-1]
            else:
                tail[col] = [stamps.iloc[-1] + step * (i + 1) for i in range(k)]
        else:
            tail[col] = df[col].iloc[-1]
    out = pd.concat([df, tail[list(df.columns)]], ignore_index=True)
    out.attrs.update(df.attrs)
    return out


def _revise(df: pd.DataFrame, bars: int) -> pd.DataFrame:
    """The last ``bars`` bars restated by a vendor: prices x1.001, volume x1.01."""
    out = df.copy()
    idx = out.index[-bars:]
    for col in ("open", "high", "low", "close"):
        out.loc[idx, col] = out.loc[idx, col].to_numpy(dtype=np.float64) * 1.001
    if "volume" in out.columns:
        out.loc[idx, "volume"] = out.loc[idx, "volume"].to_numpy(dtype=np.float64) * 1.01
    return out


def snapshot(df: pd.DataFrame, t: int, fraction: float) -> pd.DataFrame:
    """``df[:t+1]`` where bar ``t`` is shown as it stood ``fraction`` of the way through it.

    The path is open -> low -> high -> close for an up bar and open -> high -> low -> close for a down bar, in
    equal thirds; high and low are the running extremes and the close is the last price.
    """
    head = df.iloc[: t + 1].copy()
    o, h, l, c = (float(df[k].iloc[t]) for k in ("open", "high", "low", "close"))
    way = [o, l, h, c] if c >= o else [o, h, l, c]
    pos = fraction * 3.0
    seg = min(int(pos), 2)
    part = pos - seg
    price = way[seg] + (way[seg + 1] - way[seg]) * part
    passed = way[: seg + 1] + [price]
    row = {"open": o, "high": max(passed), "low": min(passed), "close": price}
    for key, val in row.items():
        head.iloc[-1, head.columns.get_loc(key)] = val
    if "volume" in head.columns:
        head.iloc[-1, head.columns.get_loc("volume")] = float(df["volume"].iloc[t]) * fraction
    head.attrs.update(df.attrs)
    return head


def probe_repaint_history(
    fn: Any, df: pd.DataFrame, full: np.ndarray, *, positions: str = "sign", mode: str = "auto"
) -> dict[str, Any]:
    """Does the signal of a closed bar move as bars arrive (prefixes, an extension, a revision)?"""
    n = len(df)
    strict = mode == "strict"
    grid = _checkpoints(n, 48 if strict else 12, None)
    points = np.union1d(grid, _decision_points(full, n, 24 if strict else 6, None))
    points = np.union1d(points, np.array([p for p in (n - 3, n - 2) if p >= 2], dtype=np.int64))
    if points.size == 0:
        return {"status": "skip", "reason": "too few bars"}
    heads = run_positions(fn, df, [Head(int(t) + 1) for t in points], positions)
    seen = [(int(t), h) for t, h in zip(points, heads, strict=True)] + [(n - 1, full)]
    moved = np.zeros(n, dtype=bool)
    events: list[dict[str, Any]] = []
    for (t0, a), (_t1, b) in zip(seen[:-1], seen[1:], strict=True):
        diff = np.flatnonzero(b[: t0 + 1] != a)
        if diff.size:
            moved[diff] = True
            events.append({"seen_at": t0, "bar": int(diff[0]), "depth": int(t0 - diff[0]), "changed_bars": int(diff.size)})
    k = max(3, min(50, n // 20))
    ext_diff, rev_diff = np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)
    errors = []
    try:  # a strategy that cannot run on a longer or restated table (it holds its own copy of the data) is not a repaint
        extended = run_positions(fn, df, [_extend(df, k)], positions)[0][:n]
        ext_diff = np.flatnonzero(extended != full)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"extension: {type(exc).__name__}")
    try:
        revised = run_positions(fn, df, [_revise(df, REVISED_BARS)], positions)[0][: n - REVISED_BARS]
        rev_diff = np.flatnonzero(revised != full[: n - REVISED_BARS])
    except Exception as exc:  # noqa: BLE001
        errors.append(f"revision: {type(exc).__name__}")
    failed = bool(events or ext_diff.size or rev_diff.size)
    compared = int(seen[-2][0] + 1) if len(seen) > 1 else n
    return {
        "status": "fail" if failed else "pass",
        "mode": mode,
        "checkpoints": int(points.size),
        "moved_bars": int(moved.sum()),
        "repaint_rate": round(float(moved.sum()) / max(1, compared), 6),
        "max_depth": max((e["depth"] for e in events), default=0),
        "first_bar": int(np.flatnonzero(moved)[0]) if moved.any() else None,
        "extension_bars": int(k),
        "extension_changed": int(ext_diff.size),
        "revision_changed": int(rev_diff.size),
        "errors": errors,
        "events": events[:MAX_REPORTED],
    }


def probe_repaint_live(
    fn: Any, df: pd.DataFrame, full: np.ndarray, *, positions: str = "sign", mode: str = "auto", timing: str = "close"
) -> dict[str, Any]:
    """Does the signal of the forming bar differ from its signal at the close?"""
    n = len(df)
    strict = mode == "strict"
    points = np.union1d(_checkpoints(n, 24 if strict else 6, None), _decision_points(full, n, 12 if strict else 3, None))
    if points.size == 0:
        return {"status": "skip", "reason": "too few bars"}
    tables = [snapshot(df, int(t), f) for t in points for f in FRACTIONS]
    try:
        out = run_positions(fn, df, tables, positions)
    except Exception as exc:  # noqa: BLE001 - the strategy cannot run on a forming bar (it holds its own copy of the data)
        return {"status": "skip", "reason": f"the strategy failed on a forming bar ({type(exc).__name__})"}
    flips = 0
    by_fraction = dict.fromkeys(FRACTIONS, 0)
    for i, got in enumerate(out):
        t = int(points[i // len(FRACTIONS)])
        f = FRACTIONS[i % len(FRACTIONS)]
        if got[-1] != full[t]:
            flips += 1
            by_fraction[f] += 1
    total = len(out)
    open_known = flips == 0
    declared_open = timing == "open"
    return {
        "status": "pass" if open_known else "fail" if declared_open else "info",
        "mode": mode,
        "timing": timing,
        "bars_checked": int(points.size),
        "snapshots": int(total),
        "flicker_rate": round(flips / total, 6),
        "known_at_open": bool(open_known),
        "flips_by_fraction": {f"{f:.2f}": c for f, c in by_fraction.items()},
    }


def _summary_history(r: dict[str, Any]) -> str:
    if r["status"] == "pass":
        return f"repaint (history): the signal of a closed bar never changed ({r['checkpoints']} prefixes, +{r['extension_bars']} bars, revised tail)"
    parts = []
    if r["moved_bars"]:
        parts.append(f"{r['moved_bars']} bars changed as bars arrived (up to {r['max_depth']} bars back, first at bar {r['first_bar']})")
    if r["extension_changed"]:
        parts.append(f"{r['extension_changed']} bars changed when {r['extension_bars']} bars were added")
    if r["revision_changed"]:
        parts.append(f"{r['revision_changed']} bars changed when the last {REVISED_BARS} bars were revised")
    return "REPAINTS: " + "; ".join(parts)


def repaint_rows(history: dict[str, Any] | None, live: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Check rows for the two repaint probes (``None``: the probe did not run)."""
    from monte_neo.verify.checks import check

    out: list[dict[str, Any]] = []
    if history is not None:
        if history["status"] == "skip":
            out.append(check("repaint_history", "lookahead", "skip", f"repaint (history): {history['reason']}", history))
        else:
            out.append(check("repaint_history", "lookahead", history["status"], _summary_history(history), history))
    if live is not None:
        if live["status"] == "skip":
            out.append(check("repaint_live", "lookahead", "skip", f"repaint (forming bar): {live['reason']}", live))
        elif live["known_at_open"]:
            out.append(check("repaint_live", "lookahead", "pass", "repaint (forming bar): the signal is known at the bar's open and cannot change while it forms", live))
        elif live["timing"] == "open":
            summary = f"the signal is declared known at the open but changes while the bar forms (flicker {live['flicker_rate']:.0%}): it needs the bar's own prices"
            out.append(check("repaint_live", "lookahead", "fail", summary, live))
        else:
            summary = f"repaint (forming bar): decided at the close, flickers while the bar forms ({live['flicker_rate']:.0%} of snapshots): act on it only after the bar closes"
            out.append(check("repaint_live", "lookahead", "info", summary, live))
    return out


__all__ = [
    "FRACTIONS", "MODES", "TIMINGS", "probe_repaint_history", "probe_repaint_live", "repaint_rows", "snapshot",
]
