"""``verify_quotes``: one certificate for a strategy run on quotes with arrival time.

Runs ``quote_quality``, ``net_profitability`` (a plain backtest on the exchange clock), ``arrival_lookahead``,
``latency_tolerance`` and ``latency_monte_carlo`` (see :mod:`monte_neo.verify.arrival`) and returns a
``strategy-verdict/1`` certificate. It does not run the OHLCV look-ahead probes: those need bars, and here the bars
depend on the clock. The certificate cannot be rechecked with ``--recheck`` yet (that command takes OHLCV); rerun
``verify_quotes`` on the same quotes to reproduce it.
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
from monte_neo.verify.quotes import Quotes, load_quotes, make_grid, quote_quality, quote_row, select_symbol
from monte_neo.verify.recheck import RECHECK_SCHEMA_ID, load_certificate
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
    commission_bps: float | None = None,
    slippage_bps: float | None = None,
    warmup_bars: int | None = None,
    samples: int = MC_SAMPLES,
    seed: int = MC_SEED,
    positions: str = "auto",
    symbol: str | None = None,
    order_latency_ms: float = 0.0,
) -> dict[str, Any]:
    """Verify a strategy against the time its quotes really arrived; returns a ``strategy-verdict/1`` report.

    ``quotes``: a table or a ``.csv`` / ``.parquet`` file with ``timestamp``, ``bid``, ``ask`` and ``latency_ms``
    (or an ``arrival`` timestamp), one instrument. ``model`` is a full execution model; or give ``commission_bps`` /
    ``slippage_bps`` / ``warmup_bars`` (default: a tenth of the bars, at most 60) on top of the verifier's defaults. ``strategy`` is ``file.py[:func]`` (runs with your permissions)
    or pass ``signal_fn``; either way ``signal(df)`` gets bars of ``open, high, low, close, volume`` and returns positions.
    A table of several symbols needs ``symbol`` (the quotes of one instrument are verified). ``order_latency_ms`` is the
    delay from the decision to the fill (the data latency comes from the quotes).
    """
    if order_latency_ms < 0:
        raise ValueError("order_latency_ms must be >= 0")
    if (strategy is None) == (signal_fn is None):
        raise ValueError("give exactly one of strategy (file.py[:func]) or signal_fn")
    if strategy is not None:
        signal_fn, source = load_signal_fn(strategy)
        source = source if source is not None else read_source(Path(str(strategy).split(":")[0]))
    q = select_symbol(load_quotes(_table(quotes)), symbol)
    n_bars = make_grid(q, bar_ms).n_bars
    if model is None:
        model = _default_model(n_bars)
        overrides = {"commission_bps": commission_bps, "slippage_bps": slippage_bps, "warmup_bars": warmup_bars}
        model = replace(model, **{k: v for k, v in overrides.items() if v is not None})
    if n_bars <= model.warmup_bars + 2:
        raise ValueError(
            f"only {n_bars} bars of {bar_ms:g} ms for a warm-up of {model.warmup_bars}: record longer or use a shorter bar_ms"
        )
    quality = quote_quality(q)
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
    checks = [quote_row(quality), profit, arrival_row(arrival), latency_row(scan), monte_carlo_row(mc)]
    metrics = {
        "quotes": quality["quotes"],
        "bar_ms": float(bar_ms),
        "order_latency_ms": float(order_latency_ms),
        "latency_p50_ms": quality["latency_ms"]["p50"],
        "latency_p95_ms": quality["latency_ms"]["p95"],
        "return_exchange_clock": arrival["return_exchange_clock"],
        "return_arrival_clock": arrival["return_arrival_clock"],
        "latency_profit_vanishes_at_extra_ms": scan["profit_vanishes_at_extra_ms"],
        "latency_probability_of_loss": mc["probability_of_loss"],
    }
    settings = {
        "bar_ms": float(bar_ms), "samples": int(samples), "seed": int(seed), "positions": positions, "kind": "quotes",
        "symbol": symbol, "order_latency_ms": float(order_latency_ms),
    }
    latency = {"arrival": arrival, "scan": scan, "monte_carlo": mc, "quality": quality}
    return _report(checks, metrics, _QuoteData(q), None, source, model, None, settings, sections={"latency": latency})


def recheck_quotes(
    certificate: dict[str, Any] | str | Path,
    quotes: pd.DataFrame | str | Path,
    *,
    strategy: str | Path | None = None,
    signal_fn: SignalFn | None = None,
) -> dict[str, Any]:
    """Reproduce a quote certificate from its quotes and strategy; ``reproduced`` is True only if everything matches.

    The settings (bar length, draws, seed, symbol, order delay) and the execution model come from the certificate.
    """
    cert = load_certificate(certificate)
    repro = cert["reproducibility"]
    s = repro.get("settings") or {}
    if s.get("kind") != "quotes":
        raise ValueError("this is not a quote certificate: use recheck_certificate with the OHLCV it was issued for")
    again = verify_quotes(
        quotes, strategy=strategy, signal_fn=signal_fn, bar_ms=s["bar_ms"], model=ExecutionModel(**repro["model"]),
        samples=s["samples"], seed=s["seed"], positions=s["positions"], symbol=s.get("symbol"),
        order_latency_ms=s.get("order_latency_ms", 0.0),
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


__all__ = ["recheck_quotes", "verify_quotes"]
