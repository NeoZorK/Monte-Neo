"""``verify_quotes``: one certificate for a strategy run on quotes with arrival time.

Runs ``quote_quality``, ``net_profitability`` (a plain backtest on the exchange clock), ``spread_cost``, the look-ahead probes
of ``verify_strategy`` on the arrival-clock bars, ``arrival_lookahead``, ``latency_tolerance`` and ``latency_monte_carlo``
(see :mod:`monte_neo.verify.arrival`) and returns a ``strategy-verdict/1`` certificate. A strategy may read several feeds
(``feeds=``): the traded instrument keeps the plain column names, every other feed gets its alias as a prefix.
The latency comes from the quotes or from an *assumed* model (``latency_model=``); the certificate says which.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo._version import __version__
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
from monte_neo.verify.quotes import (
    QuoteSet,
    assume_latency,
    feed_alias,
    info_bars,
    load_quotes,
    make_grid,
    quote_quality,
    quote_row,
    select_symbol,
)
from monte_neo.verify.quotes_probes import lookahead_rows
from monte_neo.verify.recheck import RECHECK_SCHEMA_ID, load_certificate
from monte_neo.verify.verdict import _default_model, _report

_RESERVED = {"open", "high", "low", "close", "volume"}


@dataclass(frozen=True)
class _QuoteData:
    """What ``_report`` needs from a market: a kind and the bytes that are hashed (every feed, in order)."""

    quotes: QuoteSet
    kind: str = "quotes"

    def data_bytes(self) -> bytes:
        digest = hashlib.sha256()
        for alias, q in self.quotes.feeds:
            digest.update(alias.encode())
            for a in (q.exchange_ns, q.latency_ms, q.bid, q.ask):
                digest.update(np.ascontiguousarray(a).tobytes())
        return digest.digest()


def _table(quotes: pd.DataFrame | str | Path) -> pd.DataFrame:
    if isinstance(quotes, pd.DataFrame):
        return quotes
    path = Path(quotes)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def spread_info(q: Any) -> dict[str, float]:
    """Half-spread of the traded instrument in bps of the mid (what a taker pays on each side)."""
    half = 0.5 * (q.ask - q.bid) / q.mid * 1e4
    return {"median_bps": float(np.median(half)), "p95_bps": float(np.percentile(half, 95))}


def spread_row(info: dict[str, float], model: ExecutionModel) -> dict[str, Any]:
    """``spread_cost``: the model's slippage and impact against the half-spread a taker pays on every fill."""
    modeled = float(model.slippage_bps + model.impact_bps)
    thin = modeled < info["median_bps"]
    text = (
        f"modeled slippage {modeled:.2f} bps per side is below the median half-spread {info['median_bps']:.2f} bps (p95 {info['p95_bps']:.2f})"
        if thin
        else f"modeled slippage {modeled:.2f} bps per side covers the median half-spread {info['median_bps']:.2f} bps (p95 {info['p95_bps']:.2f})"
    )
    return check("spread_cost", "economics", "warn" if thin else "pass", text, {**info, "modeled_slippage_bps": modeled})


def assumptions(model: ExecutionModel, order_latency_ms: float, latency_model: str | None, feeds: list[str]) -> list[str]:
    """What the run does and does not model, in plain words (printed in the report, not part of the certificate id)."""
    source = (
        f"Data latency is ASSUMED ({latency_model}), not measured: the verdict holds only if the real latency is not worse."
        if latency_model
        else "Data latency is the latency recorded in the quotes (stamp to receive time)."
    )
    lines = [
        "Fills are taker orders at the open of the bar after the decision, priced on the mid; there is no queue position and no partial fill, "
        "so a passive (maker) strategy cannot be validated here.",
        f"Order delay from the decision to the fill: {order_latency_ms:g} ms (a constant).",
        source,
        "The strategy reads bars of the mid price; volume is the number of quotes.",
    ]
    if feeds:
        lines.append(f"The strategy also reads {len(feeds)} other feed(s) (columns prefixed by the feed alias); each feed has its own latency.")
    return lines


def verify_quotes(
    quotes: pd.DataFrame | str | Path,
    *,
    strategy: str | Path | None = None,
    signal_fn: SignalFn | None = None,
    source: str | None = None,
    bar_ms: float = 1000.0,
    model: ExecutionModel | None = None,
    commission_bps: float | None = None,
    slippage_bps: float | None = None,
    warmup_bars: int | None = None,
    samples: int = MC_SAMPLES,
    seed: int = MC_SEED,
    positions: str = "auto",
    symbol: str | None = None,
    feeds: list[str] | None = None,
    order_latency_ms: float = 0.0,
    latency_model: str | None = None,
    probes: bool = True,
) -> dict[str, Any]:
    """Verify a strategy against the time its quotes really arrived; returns a ``strategy-verdict/1`` report.

    ``quotes``: a table or a ``.csv`` / ``.parquet`` file with ``timestamp``, ``bid``, ``ask`` and ``latency_ms``
    (or an ``arrival`` timestamp). ``strategy`` is ``file.py[:func]`` (runs with your permissions) or pass ``signal_fn``;
    either way ``signal(df)`` gets bars of ``open, high, low, close, volume`` of the traded instrument and returns positions.
    A table of several symbols needs ``symbol`` (the traded one); ``feeds`` lists other symbols the strategy reads as extra
    columns ``<alias>_open ... <alias>_volume`` (alias: :func:`~monte_neo.verify.quotes.feed_alias`). ``latency_model``
    (``constant:5`` or ``lognormal:MEDIAN,P95``) replaces the recorded latency by an assumed one. ``order_latency_ms`` is the
    delay from the decision to the fill. ``probes`` also runs the look-ahead probes of ``verify_strategy`` on the arrival bars.
    ``model`` is a full execution model; or give ``commission_bps`` / ``slippage_bps`` / ``warmup_bars``.
    """
    if order_latency_ms < 0:
        raise ValueError("order_latency_ms must be >= 0")
    if (strategy is None) == (signal_fn is None):
        raise ValueError("give exactly one of strategy (file.py[:func]) or signal_fn")
    if strategy is not None:
        signal_fn, source = load_signal_fn(strategy)
        source = source if source is not None else read_source(Path(str(strategy).split(":")[0]))
    feeds = list(feeds or [])
    if feeds and symbol is None:
        raise ValueError("feeds need symbol=... (the instrument the strategy trades)")
    table = load_quotes(_table(quotes), allow_missing_latency=latency_model is not None)
    aliases = [feed_alias(s) for s in feeds]
    if symbol in feeds or len(set(aliases)) != len(aliases) or _RESERVED & set(aliases):
        raise ValueError(f"feeds must be other symbols with distinct aliases (got {aliases})")
    main, others = select_symbol(table, symbol), [select_symbol(table, s) for s in feeds]
    if latency_model is not None:
        main = assume_latency(main, latency_model, seed=seed)
        others = [assume_latency(o, latency_model, seed=seed, salt=a) for o, a in zip(others, aliases, strict=True)]
    q = QuoteSet(main, tuple(zip(aliases, others, strict=True)))
    n_bars = make_grid(q, bar_ms).n_bars
    if model is None:
        model = _default_model(n_bars)
        overrides = {"commission_bps": commission_bps, "slippage_bps": slippage_bps, "warmup_bars": warmup_bars}
        model = replace(model, **{k: v for k, v in overrides.items() if v is not None})
    if n_bars <= model.warmup_bars + 2:
        raise ValueError(
            f"only {n_bars} bars of {bar_ms:g} ms for a warm-up of {model.warmup_bars}: record longer or use a shorter bar_ms"
        )
    quality = quote_quality(main)
    feed_quality = {a: quote_quality(o) for a, o in zip(aliases, others, strict=True)}
    kw = {"bar_ms": bar_ms, "positions": positions, "order_latency_ms": order_latency_ms}
    arrival = arrival_lookahead(q, signal_fn, model, **kw)
    scan = latency_scan(q, signal_fn, model, **kw)
    mc = latency_monte_carlo(q, signal_fn, model, samples=samples, seed=seed, **kw)
    ideal = float(arrival["return_exchange_clock"])
    profit = check(
        "net_profitability", "economics", "pass" if ideal > 0.0 else "fail",
        f"net total return {ideal:+.2%} after costs on the exchange clock (a plain backtest"
        + (f", {order_latency_ms:g} ms order delay)" if order_latency_ms else ")"),
        {"total_return": ideal},
    )
    spread = spread_info(main)
    quality_row = quote_row(quality)
    bad_feeds = [a for a, info in feed_quality.items() if info["status"] != "pass"]
    if bad_feeds:
        quality_row = {**quality_row, "status": "warn", "summary": f"{quality_row['summary']}; feed(s) with broken quotes: {', '.join(bad_feeds)}"}
    quality_row["details"] = {**quality_row["details"], "feeds": feed_quality}
    checks = [quality_row, profit, spread_row(spread, model)]
    if probes:
        checks += lookahead_rows(info_bars(q, make_grid(q, bar_ms), clock="arrival"), signal_fn, source, model, positions)
    checks += [arrival_row(arrival), latency_row(scan), monte_carlo_row(mc)]
    metrics = {
        "quotes": quality["quotes"],
        "bar_ms": float(bar_ms),
        "order_latency_ms": float(order_latency_ms),
        "latency_p50_ms": quality["latency_ms"]["p50"],
        "latency_p95_ms": quality["latency_ms"]["p95"],
        "half_spread_bps": spread["median_bps"],
        "return_exchange_clock": arrival["return_exchange_clock"],
        "return_arrival_clock": arrival["return_arrival_clock"],
        "latency_profit_vanishes_at_extra_ms": scan["profit_vanishes_at_extra_ms"],
        "latency_probability_of_loss": mc["probability_of_loss"],
    }
    settings = {
        "bar_ms": float(bar_ms), "samples": int(samples), "seed": int(seed), "positions": positions, "kind": "quotes",
        "symbol": symbol, "feeds": feeds, "order_latency_ms": float(order_latency_ms), "latency_model": latency_model,
        "probes": bool(probes),
    }
    latency = {"arrival": arrival, "scan": scan, "monte_carlo": mc, "quality": quality, "spread": spread}
    sections = {"latency": latency, "assumptions": assumptions(model, order_latency_ms, latency_model, feeds)}
    return _report(checks, metrics, _QuoteData(q), None, source, model, None, settings, sections=sections)


def recheck_quotes(
    certificate: dict[str, Any] | str | Path,
    quotes: pd.DataFrame | str | Path,
    *,
    strategy: str | Path | None = None,
    signal_fn: SignalFn | None = None,
) -> dict[str, Any]:
    """Reproduce a quote certificate from its quotes and strategy; ``reproduced`` is True only if everything matches.

    The settings (bar length, draws, seed, symbols, delays, latency model) and the execution model come from the certificate.
    """
    cert = load_certificate(certificate)
    repro = cert["reproducibility"]
    s = repro.get("settings") or {}
    if s.get("kind") != "quotes":
        raise ValueError("this is not a quote certificate: use recheck_certificate with the OHLCV it was issued for")
    again = verify_quotes(
        quotes, strategy=strategy, signal_fn=signal_fn, bar_ms=s["bar_ms"], model=ExecutionModel(**repro["model"]),
        samples=s["samples"], seed=s["seed"], positions=s["positions"], symbol=s.get("symbol"), feeds=s.get("feeds"),
        order_latency_ms=s.get("order_latency_ms", 0.0), latency_model=s.get("latency_model"), probes=s.get("probes", False),
    )
    again_repro = again["reproducibility"]
    inputs = {
        "data_sha256": again_repro["data_sha256"] == repro.get("data_sha256"),
        "source_sha256": again_repro["source_sha256"] == repro.get("source_sha256"),
    }
    same_verdict = again["verdict"] == cert.get("verdict")
    same_id = again["certificate_id"] == cert.get("certificate_id")
    report: dict[str, Any] = {
        "schema": RECHECK_SCHEMA_ID,
        "certificate_id": cert.get("certificate_id"),
        "original_verdict": cert.get("verdict"),
        "original_engine_version": repro.get("engine_version"),
        "engine_version": __version__,
        "inputs_match": inputs,
        "verdict": again["verdict"],
        "recomputed_certificate_id": again["certificate_id"],
        "verdict_matches": same_verdict,
        "certificate_id_matches": same_id,
        "reproduced": bool(all(inputs.values()) and same_verdict and same_id),
    }
    if not report["reproduced"]:
        if not all(inputs.values()):
            report["reason"] = "inputs differ from the certificate"
        elif repro.get("engine_version") != __version__:
            report["reason"] = f"certificate was issued by monte-neo {repro.get('engine_version')}; this is {__version__}"
        else:
            report["reason"] = "verdict differs" if not same_verdict else "certificate id differs"
    return report


__all__ = ["assumptions", "recheck_quotes", "spread_info", "spread_row", "verify_quotes"]
