"""Does the profit survive the time data really arrives? Arrival look-ahead, latency scan, latency Monte Carlo.

A strategy decides on what it *sees* and trades against what the market *does*. With quotes:

* **market bars** bin quotes by exchange time: the true state of the market, used for fills;
* **information bars** bin quotes by exchange time + latency: what had reached you when you decided.

A plain backtest feeds the strategy the market bars (information = market, zero latency). Here the same
``signal(df)`` is also fed the information bars, then its positions are filled on the market bars. If the
profit exists only with zero latency, it is look-ahead at millisecond scale. All three checks are context
(``warn`` at most) until they have run on the honest-strategy corpus.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.checks import check
from monte_neo.verify.engine import total_return
from monte_neo.verify.ingest import SignalFn, call_signal_fn
from monte_neo.verify.quotes import Grid, Quotes, QuoteSet, as_set, bars_from_quotes, info_bars, make_grid

SCAN_MS = (0.0, 5.0, 20.0, 50.0, 100.0, 250.0)
MC_SAMPLES = 200
MC_SEED = 42
_OHLC = ("open", "high", "low", "close")


def _frame(bars: dict[str, np.ndarray]) -> pd.DataFrame:
    """The traded feed as ``open ... volume`` first, then every other feed's columns with its alias prefix."""
    return pd.DataFrame(dict(bars))


def _return(fn: SignalFn, info: dict[str, np.ndarray], market: dict[str, np.ndarray], model: ExecutionModel, positions: str) -> float:
    """Positions from ``fn`` on the information bars, filled on the market bars."""
    signal = call_signal_fn(fn, _frame(info), positions)
    return total_return({k: market[k] for k in _OHLC}, signal, model)


def _market(q: Quotes, grid: Grid, order_latency_ms: float = 0.0) -> dict[str, np.ndarray]:
    """The bars fills are priced on; ``order_latency_ms`` is the delay from the decision to the fill."""
    return bars_from_quotes(q, grid, clock="exchange", order_latency_ms=order_latency_ms)


def arrival_lookahead(
    q: Quotes | QuoteSet, fn: SignalFn, model: ExecutionModel, *, bar_ms: float, positions: str = "sign", order_latency_ms: float = 0.0
) -> dict[str, Any]:
    """Return with zero data latency (plain backtest) against the return on arrival-time information.

    ``warn`` when the strategy is profitable on the exchange clock and loses money on the arrival clock.
    ``order_latency_ms`` delays every fill in both runs, so it lowers both returns.
    """
    qs = as_set(q)
    grid = make_grid(qs, bar_ms)
    market = _market(qs.main, grid, order_latency_ms)
    ideal = _return(fn, info_bars(qs, grid, clock="exchange"), market, model, positions)
    seen = _return(fn, info_bars(qs, grid, clock="arrival"), market, model, positions)
    if not (qs.latency_ms > 0).any():
        status = "skip"
    elif ideal <= 0.0:
        status = "skip"
    else:
        status = "warn" if seen <= 0.0 else "pass"
    return {
        "status": status,
        "bar_ms": float(bar_ms),
        "order_latency_ms": float(order_latency_ms),
        "return_exchange_clock": ideal,
        "return_arrival_clock": seen,
        "retained": (seen / ideal) if ideal > 0.0 else None,
        "median_latency_ms": float(np.median(qs.latency_ms)),
    }


def arrival_row(info: dict[str, Any]) -> dict[str, Any]:
    """The ``arrival_lookahead`` check row."""
    if info["status"] == "skip":
        why = "no latency in the quotes" if info["median_latency_ms"] <= 0 else "not profitable on the exchange clock"
        return check("arrival_lookahead", "lookahead", "skip", why, info)
    if info["status"] == "warn":
        text = f"profit {100 * info['return_exchange_clock']:.2f}% on exchange time, {100 * info['return_arrival_clock']:.2f}% on arrival time"
    else:
        text = f"keeps {100 * info['retained']:.0f}% of the profit when data is binned by arrival time"
    return check("arrival_lookahead", "lookahead", info["status"], text, info)


def latency_scan(
    q: Quotes | QuoteSet,
    fn: SignalFn,
    model: ExecutionModel,
    *,
    bar_ms: float,
    extra_ms: tuple[float, ...] = SCAN_MS,
    positions: str = "sign",
    order_latency_ms: float = 0.0,
) -> dict[str, Any]:
    """Return when data arrives ``extra_ms`` later than it did, plus the delay where the profit disappears.

    The observed p95 latency is always scanned. The profit has *vanished* at the smallest extra delay whose return and the
    next scanned delay's return are both not positive (one noisy point of a thin edge does not count).
    ``warn`` when it has vanished by one more p95 of delay (a slow day).
    """
    qs = as_set(q)
    p95 = float(np.percentile(qs.latency_ms, 95))
    points = sorted({float(x) for x in extra_ms} | {p95})
    grid = make_grid(qs, bar_ms, max_extra_ms=points[-1])
    market = _market(qs.main, grid, order_latency_ms)
    returns = {x: _return(fn, info_bars(qs, grid, clock="arrival", extra_latency_ms=x), market, model, positions) for x in points}
    base = returns[0.0] if 0.0 in returns else _return(fn, info_bars(qs, grid, clock="arrival"), market, model, positions)
    vanish = None
    if base > 0.0:
        later = [x for x in points if x > 0.0]
        values = [returns[x] for x in later]
        for i, x in enumerate(later):  # gone at x: this scanned delay and the next one both earn nothing
            if values[i] <= 0.0 and (i == len(later) - 1 or values[i + 1] <= 0.0):
                vanish = x
                break
    status = "skip" if base <= 0.0 else ("warn" if vanish is not None and vanish <= p95 else "pass")
    return {
        "status": status,
        "bar_ms": float(bar_ms),
        "p95_latency_ms": p95,
        "return_by_extra_ms": {f"{x:g}": r for x, r in returns.items()},
        "profit_vanishes_at_extra_ms": vanish,
    }


def latency_row(info: dict[str, Any]) -> dict[str, Any]:
    """The ``latency_tolerance`` check row."""
    if info["status"] == "skip":
        return check("latency_tolerance", "economics", "skip", "not profitable on the observed arrival clock", info)
    vanish = info["profit_vanishes_at_extra_ms"]
    where = "survives every scanned delay" if vanish is None else f"profit vanishes at about {vanish:.0f} ms of extra delay"
    return check("latency_tolerance", "economics", info["status"], f"{where} (observed p95 latency {info['p95_latency_ms']:.0f} ms)", info)


def latency_monte_carlo(
    q: Quotes | QuoteSet,
    fn: SignalFn,
    model: ExecutionModel,
    *,
    bar_ms: float,
    samples: int = MC_SAMPLES,
    seed: int = MC_SEED,
    positions: str = "sign",
    order_latency_ms: float = 0.0,
) -> dict[str, Any]:
    """Distribution of the return when each quote's latency is redrawn from the observed latencies.

    Draws stay inside a venue when the quotes carry one. The seed is fixed, so the result is reproducible
    and can sit in a certificate. ``warn`` when most draws lose money although the observed sample earns.
    """
    rng = np.random.default_rng(seed)
    qs = as_set(q)
    grid = make_grid(qs, bar_ms, max_extra_ms=float(qs.latency_ms.max()))
    market = _market(qs.main, grid, order_latency_ms)
    observed = _return(fn, info_bars(qs, grid, clock="arrival"), market, model, positions)
    groups = {
        alias: [np.arange(len(f))] if f.venue is None else [np.flatnonzero(f.venue == v) for v in sorted(set(f.venue.tolist()))]
        for alias, f in qs.feeds
    }
    returns = np.empty(int(samples))
    for s in range(int(samples)):
        draws: dict[str, np.ndarray] = {}
        for alias, f in qs.feeds:  # every feed redraws its own latency, inside its venue
            lat = np.empty(len(f))
            for g in groups[alias]:
                lat[g] = rng.choice(f.latency_ms[g], size=g.size, replace=True)
            draws[alias] = lat
        returns[s] = _return(fn, info_bars(qs, grid, clock="arrival", latency_overrides=draws), market, model, positions)
    p5, p50, p95 = (float(x) for x in np.percentile(returns, [5, 50, 95]))
    loss = float((returns <= 0.0).mean())
    return {
        "status": "skip" if observed <= 0.0 else ("warn" if loss > 0.5 else "pass"),
        "bar_ms": float(bar_ms),
        "samples": int(samples),
        "seed": int(seed),
        "observed_return": observed,
        "return_p5": p5,
        "return_p50": p50,
        "return_p95": p95,
        "probability_of_loss": loss,
    }


def monte_carlo_row(info: dict[str, Any]) -> dict[str, Any]:
    """The ``latency_monte_carlo`` check row."""
    if info["status"] == "skip":
        return check("latency_monte_carlo", "statistics", "skip", "not profitable on the observed arrival clock", info)
    text = f"{100 * info['probability_of_loss']:.0f}% of {info['samples']} latency draws lose money (median {100 * info['return_p50']:.2f}%)"
    return check("latency_monte_carlo", "statistics", info["status"], text, info)


__all__ = [
    "arrival_lookahead",
    "arrival_row",
    "latency_monte_carlo",
    "latency_row",
    "latency_scan",
    "monte_carlo_row",
]
