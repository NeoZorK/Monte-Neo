"""Event-data quality and the point-in-time check row (``lookahead``)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.checks import check
from monte_neo.verify.events import bar_times

NEXT_ACTIONS: dict[str, str] = {
    "events_quality": "Fix the events table: published_at must be the real time the information became public, never a copy of event_time and never earlier than it. Re-export it from the vendor's first-release timestamps.",
    "pit_events": "The profit needs events joined by the time they happened. Join your events by publication time (plus your real processing delay), then re-run; the verifier already does so.",
}

SAME_BAR_WARN = 0.95
WARN_RATIO = 2.0
WARN_GAP_PP = 5.0


def events_quality(events: pd.DataFrame, ohlcv: pd.DataFrame | None = None) -> dict[str, Any]:
    """Describe how credible the publication times are.

    Args:
        events: Output of ``load_events``.
        ohlcv: Optional bars; adds the out-of-range count and the same-bar share.

    Returns:
        Counts and shares: ``n``, ``published_before_event``, ``no_event_time``,
        ``delay_median_s`` / ``delay_p95_s`` (published_at - event_time, seconds),
        ``outside_range`` and ``same_bar_share`` (None when not computable).
    """
    n = len(events)
    pub = events["published_at"]
    info: dict[str, Any] = {"n": n, "published_before_event": 0, "no_event_time": n, "delay_median_s": None,
                            "delay_p95_s": None, "outside_range": None, "same_bar_share": None}
    if "event_time" in events.columns:
        ev = events["event_time"]
        has = ev.notna()
        info["no_event_time"] = int((~has).sum())
        delay = (pub[has] - ev[has]).dt.total_seconds().to_numpy()
        if len(delay):
            info["published_before_event"] = int(np.count_nonzero(delay < 0))
            info["delay_median_s"] = float(np.median(delay))
            info["delay_p95_s"] = float(np.percentile(delay, 95))
    if ohlcv is not None and n:
        bars = np.sort(bar_times(ohlcv).dropna().unique())
        if len(bars):
            info["outside_range"] = int(np.count_nonzero((pub.to_numpy() < bars[0]) | (pub.to_numpy() > bars[-1])))
            if "event_time" in events.columns and bool(events["event_time"].notna().any()):
                both = events.dropna(subset=["event_time"])
                b_pub = np.searchsorted(bars, both["published_at"].to_numpy(), side="right")
                b_ev = np.searchsorted(bars, both["event_time"].to_numpy(), side="right")
                info["same_bar_share"] = float(np.mean(b_pub == b_ev))
    return info


def events_quality_row(events: pd.DataFrame, ohlcv: pd.DataFrame | None = None) -> dict[str, Any]:
    """Integrity row for the events table: ``events_quality``."""
    info = events_quality(events, ohlcv)
    n = max(info["n"], 1)
    warns: list[str] = []
    if info["published_before_event"]:
        share = info["published_before_event"] / n
        warns.append(f"{share:.0%} of events are published before they happened (published_at < event_time): impossible, the timestamps are wrong")
    same = info["same_bar_share"]
    if info["delay_median_s"] is not None and (info["delay_median_s"] <= 0 or (same is not None and same >= SAME_BAR_WARN)):
        warns.append("no publication delay at all: check that published_at is the real publication time, not a copy of event_time")
    if info["outside_range"]:
        warns.append(f"{info['outside_range']} events fall outside the OHLCV range")
    if info["no_event_time"] == info["n"]:
        summary = "events have no event_time column: the publication-time join cannot be compared with the leaky one"
    elif warns:
        summary = "; ".join(warns)
    else:
        med = info["delay_median_s"]
        summary = f"{info['n']} events, median publication delay {med / 3600:.1f} h" if med is not None else f"{info['n']} events"
    return check("events_quality", "integrity", "warn" if warns else "pass", summary, info)


def pit_events_row(profit_published: float | None, profit_event_time: float | None, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compare net total return joined by publication time vs by event time.

    Args:
        profit_published: Net total return (fraction) with the honest join; what the verifier tests.
        profit_event_time: Net total return with the leaky join; ``None`` when there is no event_time.
        details: Extra fields to keep in the row.

    Returns:
        A ``pit_events`` row: ``skip`` without event_time, ``warn`` when the leaky join earns
        more than 2x and more than 5 percentage points above the honest one, else ``info``.
    """
    det = dict(details or {})
    if profit_event_time is None or profit_published is None or not (np.isfinite(profit_event_time) and np.isfinite(profit_published)):
        return check("pit_events", "lookahead", "skip", "no event_time column: cannot show what a join by event time would earn", det)
    gap = (profit_event_time - profit_published) * 100.0
    det.update({"profit_published": float(profit_published), "profit_event_time": float(profit_event_time), "gap_pp": float(gap)})
    leaky = profit_event_time > WARN_RATIO * profit_published and gap > WARN_GAP_PP
    if leaky:
        msg = (f"joining events by event time would earn {profit_event_time:.1%} vs {profit_published:.1%} by publication time "
               f"(+{gap:.1f} pp): most of this edge would exist only if you knew events before they were published: "
               "make sure your own pipeline joins by publication time")
        return check("pit_events", "lookahead", "warn", msg, det)
    msg = f"net return {profit_published:.1%} joined by publication time, {profit_event_time:.1%} by event time ({gap:+.1f} pp)"
    return check("pit_events", "lookahead", "info", msg, det)
