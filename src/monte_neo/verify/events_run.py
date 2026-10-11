"""``verify_strategy(events=...)``: join events by publication time and price the leaky join.

The verifier joins the events itself, by ``published_at`` (plus an optional delay), so the strategy can only see an
event after it was public. With an ``event_time`` column the same strategy also runs once on the leaky join (events
visible from the moment they happened); the ``pit_events`` row shows how much of the profit would exist only there.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.events import join_events, load_events
from monte_neo.verify.events_checks import events_quality_row, pit_events_row


def prepare_events(
    df: pd.DataFrame, events: Any, delay_seconds: float
) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame, str]:
    """Load the events and join them to the OHLCV.

    Args:
        df: The OHLCV the strategy receives.
        events: An events table or a path (see :func:`monte_neo.verify.events.load_events`).
        delay_seconds: Extra delay after publication before an event is usable.

    Returns:
        (OHLCV joined by publication time, OHLCV joined by event time or ``None``, the events, their sha256).
    """
    if delay_seconds < 0:
        raise ValueError(f"events_delay must be >= 0 seconds, got {delay_seconds}")
    ev = load_events(events)
    digest = hashlib.sha256(pd.util.hash_pandas_object(ev, index=False).to_numpy().tobytes()).hexdigest()
    delay = pd.Timedelta(seconds=float(delay_seconds))
    joined = join_events(df, ev, by="published_at", delay=delay)
    joined.attrs.update(df.attrs)
    leaky = None
    if "event_time" in ev.columns and ev["event_time"].notna().any():
        leaky = join_events(df, ev.dropna(subset=["event_time"]), by="event_time")
        leaky.attrs.update(df.attrs)
    return joined, leaky, ev, digest


def net_result(frame: pd.DataFrame, fn: Any, model: ExecutionModel, positions: str, values: Any = None) -> dict[str, float]:
    """Net total return and annualised Sharpe of ``fn`` (or of given ``values``) on ``frame``, through the verifier's engine."""
    from monte_neo.verify.engine import simulate
    from monte_neo.verify.ingest import resolve_positions
    from monte_neo.verify.market import market_for
    from monte_neo.verify.stats import bar_returns, infer_periods_per_year, sharpe_per_bar

    market = market_for(frame)
    raw = market.read_values(fn if values is None else None, values)
    mode = resolve_positions(raw, positions)
    sig, _ = market.positions(raw, mode, model)
    run = simulate(market.ohlc, sig, model)
    rets = bar_returns(run["equity"], start=model.warmup_bars)
    sharpe = float(sharpe_per_bar(rets) * np.sqrt(infer_periods_per_year(market.timestamps)))
    return {"total_return": float(run["total_return"]), "sharpe": sharpe if np.isfinite(sharpe) else 0.0}


def _net_return(frame: pd.DataFrame, fn: Any, model: ExecutionModel, positions: str) -> float:
    return net_result(frame, fn, model, positions)["total_return"]


def events_rows(
    joined: pd.DataFrame, leaky: pd.DataFrame | None, ev: pd.DataFrame, fn: Any, model: ExecutionModel, positions: str
) -> list[dict[str, Any]]:
    """The ``events_quality`` row and the ``pit_events`` row (``fn`` must run in this process; ``None`` skips it)."""
    rows = [events_quality_row(ev, joined)]
    if leaky is None or fn is None:
        reason = "no event_time column" if leaky is None else "needs strategy code that can run in this process (not --isolate)"
        row = pit_events_row(float("nan"), None, {"reason": reason})
        if leaky is not None:
            row["summary"] = f"the event-time comparison was not run: it {reason}"
        rows.append(row)
        return rows
    published = _net_return(joined, fn, model, positions)
    at_event = _net_return(leaky, fn, model, positions)
    rows.append(pit_events_row(published, at_event if np.isfinite(at_event) else None, {"columns": [c for c in joined if c.startswith("ev_")]}))
    return rows


__all__ = ["events_rows", "net_result", "prepare_events"]
