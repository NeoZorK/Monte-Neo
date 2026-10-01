"""``verify_quotes``: one certificate for a strategy run on quotes with arrival time.

Runs ``quote_quality``, ``net_profitability`` (a plain backtest on the exchange clock), ``arrival_lookahead``,
``latency_tolerance`` and ``latency_monte_carlo`` (see :mod:`monte_neo.verify.arrival`) and returns a
``strategy-verdict/1`` certificate. It does not run the OHLCV look-ahead probes: those need bars, and here the bars
depend on the clock. The certificate cannot be rechecked with ``--recheck`` yet (that command takes OHLCV); rerun
``verify_quotes`` on the same quotes to reproduce it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.arrival import (
    MC_SAMPLES,
    MC_SEED,
    arrival_lookahead,
    arrival_row,
    latency_monte_carlo,
    latency_row,
    latency_scan,
    monte_carlo_row,
)
from monte_neo.verify.checks import check
from monte_neo.verify.ingest import SignalFn, load_signal_fn
from monte_neo.verify.limits import read_source
from monte_neo.verify.quotes import Quotes, load_quotes, make_grid, quote_quality, quote_row
from monte_neo.verify.verdict import _default_model, _report


@dataclass(frozen=True)
class _QuoteData:
    """What ``_report`` needs from a market: a kind and the bytes that are hashed."""

    quotes: Quotes
    kind: str = "quotes"

    def data_bytes(self) -> bytes:
        q = self.quotes
        return hashlib.sha256(
            b"".join(np.ascontiguousarray(a).tobytes() for a in (q.exchange_ns, q.latency_ms, q.bid, q.ask))
        ).digest()


def _table(quotes: pd.DataFrame | str | Path) -> pd.DataFrame:
    if isinstance(quotes, pd.DataFrame):
        return quotes
    path = Path(quotes)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def verify_quotes(
    quotes: pd.DataFrame | str | Path,
    *,
    strategy: str | Path | None = None,
    signal_fn: SignalFn | None = None,
    source: str | None = None,
    bar_ms: float = 1000.0,
    model: ExecutionModel | None = None,
    samples: int = MC_SAMPLES,
    seed: int = MC_SEED,
    positions: str = "auto",
) -> dict[str, Any]:
    """Verify a strategy against the time its quotes really arrived; returns a ``strategy-verdict/1`` report.

    ``quotes``: a table or a ``.csv`` / ``.parquet`` file with ``timestamp``, ``bid``, ``ask`` and ``latency_ms``
    (or an ``arrival`` timestamp), one instrument. ``strategy`` is ``file.py[:func]`` (runs with your permissions)
    or pass ``signal_fn``; either way ``signal(df)`` gets bars of ``open, high, low, close, volume`` and returns positions.
    """
    if (strategy is None) == (signal_fn is None):
        raise ValueError("give exactly one of strategy (file.py[:func]) or signal_fn")
    if strategy is not None:
        signal_fn, source = load_signal_fn(strategy)
        source = source if source is not None else read_source(Path(str(strategy).split(":")[0]))
    q = load_quotes(_table(quotes))
    n_bars = make_grid(q, bar_ms).n_bars
    model = model or _default_model(n_bars)
    if n_bars <= model.warmup_bars + 2:
        raise ValueError(
            f"only {n_bars} bars of {bar_ms:g} ms for a warm-up of {model.warmup_bars}: record longer or use a shorter bar_ms"
        )
    quality = quote_quality(q)
    arrival = arrival_lookahead(q, signal_fn, model, bar_ms=bar_ms, positions=positions)
    scan = latency_scan(q, signal_fn, model, bar_ms=bar_ms, positions=positions)
    mc = latency_monte_carlo(q, signal_fn, model, bar_ms=bar_ms, samples=samples, seed=seed, positions=positions)
    ideal = float(arrival["return_exchange_clock"])
    profit = check(
        "net_profitability", "economics", "pass" if ideal > 0.0 else "fail",
        f"net total return {ideal:+.2%} after costs on the exchange clock (a plain backtest)", {"total_return": ideal},
    )
    checks = [quote_row(quality), profit, arrival_row(arrival), latency_row(scan), monte_carlo_row(mc)]
    metrics = {
        "quotes": quality["quotes"],
        "bar_ms": float(bar_ms),
        "latency_p50_ms": quality["latency_ms"]["p50"],
        "latency_p95_ms": quality["latency_ms"]["p95"],
        "return_exchange_clock": arrival["return_exchange_clock"],
        "return_arrival_clock": arrival["return_arrival_clock"],
        "latency_profit_vanishes_at_extra_ms": scan["profit_vanishes_at_extra_ms"],
        "latency_probability_of_loss": mc["probability_of_loss"],
    }
    settings = {"bar_ms": float(bar_ms), "samples": int(samples), "seed": int(seed), "positions": positions, "kind": "quotes"}
    latency = {"arrival": arrival, "scan": scan, "monte_carlo": mc, "quality": quality}
    return _report(checks, metrics, _QuoteData(q), None, source, model, None, settings, sections={"latency": latency})


__all__ = ["verify_quotes"]
