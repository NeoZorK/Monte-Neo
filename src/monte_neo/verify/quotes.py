"""Top-of-book quotes with arrival time: load, check, and build bars on either clock.

A quote has two times: when the exchange stamped it (``timestamp``) and when it reached you
(``timestamp + latency``). A backtest that bins quotes by exchange time lets a strategy act on
prices it could not have seen yet. This module keeps both clocks so ``verify.arrival`` can compare them.

Columns (aliases in brackets): ``timestamp``, ``bid`` (``bid_price``), ``ask`` (``ask_price``),
and the delay as ``latency_ms`` (``latency``) or an ``arrival`` timestamp. Optional: ``symbol`` (``ticker``),
``venue`` (the part after ``@`` in a ticker such as ``BTC-USDT-SWAP@BINANCE``).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.checks import check

_NS_PER_MS = 1_000_000
_ALIASES = {"bid_price": "bid", "ask_price": "ask", "latency": "latency_ms", "ticker": "symbol"}
STALE_MS = 20.0
BURSTY_RATIO = 20.0  # p99 latency over the median: beyond this the latency is queueing, not the path
BURSTY_MIN_QUOTES = 100  # percentiles of fewer quotes say nothing about bursts


@dataclass(frozen=True)
class Quotes:
    """Quotes sorted by exchange time; times are int64 nanoseconds, latency is in milliseconds."""

    exchange_ns: np.ndarray
    latency_ms: np.ndarray
    bid: np.ndarray
    ask: np.ndarray
    venue: np.ndarray | None = None
    dropped: int = 0  # rows that did not parse and were left out
    symbol: np.ndarray | None = None

    def __len__(self) -> int:
        return int(self.exchange_ns.size)

    @property
    def mid(self) -> np.ndarray:
        return 0.5 * (self.bid + self.ask)

    @property
    def arrival_ns(self) -> np.ndarray:
        return self.exchange_ns + np.rint(self.latency_ms * _NS_PER_MS).astype(np.int64)


@dataclass(frozen=True)
class Grid:
    """Bar edges shared by every clock, so bars of different clocks line up one to one."""

    start_ns: int
    bar_ns: int
    n_bars: int


def _to_time(values: pd.Series) -> pd.Series:
    """UTC times; a format is never guessed from the first row (that would turn later rows into NaT)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = pd.to_datetime(values, utc=True, errors="coerce", format="ISO8601")
        if out.isna().any():
            out = out.fillna(pd.to_datetime(values, utc=True, errors="coerce", format="mixed"))
    return out


def load_quotes(table: pd.DataFrame) -> Quotes:
    """Quotes from a table; raises ``ValueError`` naming what is missing."""
    df = table.rename(columns={k: v for k, v in _ALIASES.items() if k in table.columns and v not in table.columns})
    missing = [c for c in ("timestamp", "bid", "ask") if c not in df.columns]
    if missing:
        raise ValueError(f"quotes need columns {missing} (got {list(table.columns)})")
    exchange = _to_time(df["timestamp"])
    if "latency_ms" in df.columns:
        latency = pd.to_numeric(df["latency_ms"], errors="coerce").to_numpy(dtype=np.float64)
    elif "arrival" in df.columns:
        arrival = _to_time(df["arrival"])
        latency = ((arrival - exchange).dt.total_seconds() * 1000.0).to_numpy(dtype=np.float64)
    else:
        raise ValueError("quotes need a latency_ms column (or an arrival timestamp column)")
    bid = pd.to_numeric(df["bid"], errors="coerce").to_numpy(dtype=np.float64)
    ask = pd.to_numeric(df["ask"], errors="coerce").to_numpy(dtype=np.float64)
    ok = exchange.notna().to_numpy() & np.isfinite(latency) & np.isfinite(bid) & np.isfinite(ask)
    if not ok.any():
        raise ValueError("no usable quote rows (timestamp, bid, ask, latency must all parse)")
    symbol = df["symbol"].astype(str).to_numpy() if "symbol" in df.columns else None
    venue = None
    if "venue" in df.columns:
        venue = df["venue"].astype(str).to_numpy()
    elif "symbol" in df.columns and df["symbol"].astype(str).str.contains("@").any():
        venue = df["symbol"].astype(str).str.rsplit("@", n=1).str[-1].to_numpy()
    ns = exchange.to_numpy(dtype="datetime64[ns]").astype(np.int64)
    order = np.argsort(ns[ok], kind="stable")
    pick = lambda a: a[ok][order]  # noqa: E731
    return Quotes(
        pick(ns), pick(latency), pick(bid), pick(ask),
        None if venue is None else pick(venue), int((~ok).sum()), None if symbol is None else pick(symbol),
    )


def select_symbol(q: Quotes, symbol: str | None = None) -> Quotes:
    """The quotes of one instrument. A table of several symbols needs ``symbol``; one symbol needs nothing."""
    if q.symbol is None:
        if symbol is not None:
            raise ValueError("the quotes have no symbol column to select from")
        return q
    names, counts = np.unique(q.symbol, return_counts=True)
    if symbol is None:
        if names.size == 1:
            return q
        top = ", ".join(f"{n} ({c})" for n, c in sorted(zip(names, counts, strict=True), key=lambda x: -x[1])[:5])
        raise ValueError(f"the quotes hold {names.size} symbols: pass symbol=... (most quotes: {top})")
    if symbol not in names:
        raise ValueError(f"symbol {symbol!r} is not in the quotes (found {names.size}: {', '.join(names[:5])})")
    keep = q.symbol == symbol
    return Quotes(
        q.exchange_ns[keep], q.latency_ms[keep], q.bid[keep], q.ask[keep],
        None if q.venue is None else q.venue[keep], 0, q.symbol[keep],
    )


def quote_quality(q: Quotes, *, stale_ms: float = STALE_MS) -> dict[str, Any]:
    """Counts of broken quotes and the latency profile; ``status`` is ``warn`` for broken data only."""
    n = len(q)
    crossed = int((q.bid > q.ask).sum())
    locked = int((q.bid == q.ask).sum())
    bad_price = int(((q.bid <= 0) | (q.ask <= 0)).sum())
    negative = int((q.latency_ms < 0).sum())
    arrival = q.arrival_ns
    late = int((arrival < np.maximum.accumulate(arrival)).sum())  # arrived before a quote stamped earlier
    pct = np.percentile(q.latency_ms, [50, 95, 99])
    info: dict[str, Any] = {
        "quotes": n,
        "dropped_rows": int(q.dropped),
        "crossed": crossed,
        "locked": locked,
        "non_positive_price": bad_price,
        "negative_latency": negative,
        "out_of_order_arrivals": late,
        "share_out_of_order_arrivals": late / n,
        "latency_ms": {"p50": float(pct[0]), "p95": float(pct[1]), "p99": float(pct[2])},
        "stale_ms": float(stale_ms),
        "share_stale": float((q.latency_ms > stale_ms).mean()),
    }
    ratio = float(pct[2] / pct[0]) if pct[0] > 0 and n >= BURSTY_MIN_QUOTES else None
    info["latency_p99_over_p50"] = ratio
    bursty = ratio is not None and ratio > BURSTY_RATIO
    info["bursty_latency"] = bool(bursty)
    if q.venue is not None:
        info["latency_p50_ms_by_venue"] = {
            str(v): float(np.median(q.latency_ms[q.venue == v])) for v in sorted(set(q.venue.tolist()))
        }
    broken = crossed / n > 0.001 or bad_price > 0 or negative > 0 or q.dropped > 0 or bursty
    info["status"] = "warn" if broken else "pass"
    return info


def quote_row(info: dict[str, Any]) -> dict[str, Any]:
    """The ``quote_quality`` check row."""
    lat = info["latency_ms"]
    if info["status"] == "warn":
        summary = (
            f"{info['crossed']} crossed, {info['non_positive_price']} non-positive, "
            f"{info['negative_latency']} negative-latency quotes, {info['dropped_rows']} unparseable rows dropped"
        )
        if info["bursty_latency"]:
            summary += (
                f"; latency p99 is {info['latency_p99_over_p50']:.0f}x its median: messages queue up on the path "
                "(VPN, Wi-Fi, congestion) and arrive in bursts, so the arrival checks would measure your network, not the exchange"
            )
    else:
        summary = (
            f"{info['quotes']} quotes; latency p50 {lat['p50']:.1f} ms, p95 {lat['p95']:.1f} ms; "
            f"{100 * info['share_stale']:.0f}% older than {info['stale_ms']:g} ms"
        )
    return check("quote_quality", "integrity", info["status"], summary, info)


def make_grid(q: Quotes, bar_ms: float, *, max_extra_ms: float = 0.0) -> Grid:
    """Bar grid covering both clocks (arrival plus ``max_extra_ms`` of extra delay)."""
    if not bar_ms > 0:
        raise ValueError("bar_ms must be positive")
    bar_ns = max(1, int(round(bar_ms * _NS_PER_MS)))
    start = int(q.exchange_ns[0] // bar_ns * bar_ns)
    end = int(max(q.exchange_ns[-1], q.arrival_ns.max() + int(max_extra_ms * _NS_PER_MS)))
    return Grid(start, bar_ns, int((end - start) // bar_ns) + 1)


def bars_from_quotes(
    q: Quotes,
    grid: Grid,
    *,
    clock: str = "exchange",
    extra_latency_ms: float = 0.0,
    latency_ms: np.ndarray | None = None,
    order_latency_ms: float = 0.0,
) -> dict[str, np.ndarray]:
    """Mid-price OHLC per bar with the quote's ``volume`` (a count of quotes).

    ``clock="exchange"`` bins by the exchange stamp (what a plain backtest does); ``"arrival"`` bins by
    stamp + latency + ``extra_latency_ms`` (what you could have seen). ``latency_ms`` overrides the
    per-quote latency (used to resample it). ``order_latency_ms`` (exchange clock only) moves the market bars: a
    fill at the open of a bar happens that many ms later, at the price the market had then. Empty bars repeat the
    previous close, flat, with zero volume.
    """
    if clock not in ("exchange", "arrival"):
        raise ValueError(f"clock must be 'exchange' or 'arrival', got {clock!r}")
    if clock == "exchange":
        when = q.exchange_ns - int(round(float(order_latency_ms) * _NS_PER_MS))
    else:
        lat = q.latency_ms if latency_ms is None else np.asarray(latency_ms, dtype=np.float64)
        when = q.exchange_ns + np.rint((lat + float(extra_latency_ms)) * _NS_PER_MS).astype(np.int64)
    idx = np.clip((when - grid.start_ns) // grid.bar_ns, 0, grid.n_bars - 1)
    order = np.lexsort((when, idx))
    mid, idx = q.mid[order], idx[order]
    first = np.flatnonzero(np.r_[True, idx[1:] != idx[:-1]])
    slots = idx[first]
    out = {k: np.full(grid.n_bars, np.nan) for k in ("open", "high", "low", "close")}
    out["open"][slots] = mid[first]
    out["high"][slots] = np.maximum.reduceat(mid, first)
    out["low"][slots] = np.minimum.reduceat(mid, first)
    out["close"][slots] = mid[np.r_[first[1:], mid.size] - 1]
    volume = np.zeros(grid.n_bars)
    volume[slots] = np.diff(np.r_[first, mid.size])
    close = pd.Series(out["close"]).ffill().bfill().to_numpy()
    empty = np.isnan(out["open"])
    for key in ("open", "high", "low"):
        out[key] = np.where(empty, close, out[key])
    out["close"] = close
    out["volume"] = volume
    return out


def synthetic_quotes(
    n: int = 20_000,
    *,
    seed: int = 7,
    rho: float = 0.3,
    step_ms: float = 10.0,
    median_latency_ms: float = 20.0,
    drift: float = 0.0,
    regime_steps: int = 500,
) -> pd.DataFrame:
    """Quotes of one instrument, a return every ``step_ms`` with autocorrelation ``rho`` and lognormal latency in 5-275 ms.

    ``drift`` adds a per-step trend whose sign flips about every ``regime_steps`` steps (a slow, honest edge).
    """
    rng = np.random.default_rng(seed)
    regime = 1.0 - 2.0 * (np.cumsum(rng.random(n) < 1.0 / max(1, regime_steps)) % 2)
    shocks = rng.normal(0.0, 2e-4, n) + drift * regime
    rets = pd.Series(shocks).ewm(alpha=1.0 - rho, adjust=False).mean().to_numpy() / (1.0 - rho)  # AR(1) filter
    mid = 100.0 * np.exp(np.cumsum(rets))
    stamp = pd.Timestamp("2025-10-02 00:00:00", tz="UTC") + pd.to_timedelta(np.arange(n) * step_ms, unit="ms")
    latency = np.clip(rng.lognormal(np.log(median_latency_ms), 0.6, n), 5.0, 275.0)
    return pd.DataFrame(
        {"timestamp": stamp, "bid": mid * (1 - 1e-5), "ask": mid * (1 + 1e-5), "latency_ms": latency, "symbol": "SYN-USDT@SIM"}
    )


__all__ = [
    "Grid",
    "Quotes",
    "bars_from_quotes",
    "load_quotes",
    "make_grid",
    "select_symbol",
    "quote_quality",
    "quote_row",
    "synthetic_quotes",
]
