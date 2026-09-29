"""``verify_strategy`` — the one-call verifier behind CLI, MCP and CI."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo._version import __version__
from monte_neo.backtest.bar_engine import run_bar_backtest
from monte_neo.backtest.jit import warn_if_slow
from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify import checks as rows
from monte_neo.verify.breakdown import buy_and_hold, periods, regimes, series
from monte_neo.verify.costs import breakeven_cost_bps, delay_scan
from monte_neo.verify.engine import is_weights, simulate
from monte_neo.verify.executor import ProcessRunner, resolve_jobs, split_spec
from monte_neo.verify.ingest import (
    POSITION_MODES,
    SignalFn,
    load_ohlcv,
    load_signal_fn,
    resolve_positions,
    to_positions,
)
from monte_neo.verify.io_guard import IOWatch
from monte_neo.verify.limits import read_source
from monte_neo.verify.lint import lint_source
from monte_neo.verify.market import SingleMarket, UniverseMarket, market_for
from monte_neo.verify.quality import data_quality, quality_row, spike_profit_share
from monte_neo.verify.report_data import MAX_TRADES_FOR_STATS, build_charts
from monte_neo.verify.schema import DISCLAIMER, VERDICT_SCHEMA_ID, aggregate_verdict, to_jsonable
from monte_neo.verify.stats import bar_returns, deflated_sharpe, infer_periods_per_year, sharpe_per_bar
from monte_neo.verify.timing import timing_significance


def _sha256(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.hexdigest()


def _holdout(rets: np.ndarray, fraction: float) -> dict[str, Any]:
    cut = int(round(rets.size * (1.0 - float(fraction))))
    train, hold = rets[:cut], rets[cut:]
    return {
        "holdout_fraction": float(fraction),
        "train_bars": int(train.size),
        "holdout_bars": int(hold.size),
        "train_sharpe": sharpe_per_bar(train),
        "holdout_sharpe": sharpe_per_bar(hold),
    }


def _default_model(n_bars: int) -> ExecutionModel:
    # Signals are +1 / 0 / -1 everywhere (CLI, MCP, docs): shorts must trade by default.
    return ExecutionModel(side_mode="long_short", warmup_bars=max(0, min(60, n_bars // 10)))


def _resolve_strategy(
    strategy: str | Path | None, signal_fn: SignalFn | None, source: str | None
) -> tuple[SignalFn | None, str | None]:
    if strategy is not None:
        fn, text = load_signal_fn(strategy)
        return fn, source if source is not None else text
    return signal_fn, source


def verify_strategy(
    ohlcv: pd.DataFrame | str | Path,
    *,
    signals: Any = None,
    strategy: str | Path | None = None,
    signal_fn: SignalFn | None = None,
    source: str | None = None,
    model: ExecutionModel | None = None,
    n_trials: int | None = None,
    trial_sharpes: Any = None,
    periods_per_year: float | None = None,
    holdout_fraction: float = 0.3,
    min_trades: int = 30,
    probe_checks: int = 24,
    positions: str = "auto",
    extra_checks: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
    io_watch: IOWatch | None = None,
    jobs: int | str | None = 1,
    timeout: float | None = None,
    isolate: bool = False,
) -> dict[str, Any]:
    """Verify one strategy and return a ``strategy-verdict/1`` report.

    Provide either ``signals`` (positions per bar) or strategy code via
    ``strategy`` (``file.py[:func]``) / ``signal_fn``. Code enables the
    look-ahead probes; ``source`` (or the strategy file) enables static lint.
    ``n_trials`` is how many variants were tried before picking this one.
    ``positions`` reads the signal as ``sign`` (+1 / 0 / -1), ``weight`` (fraction of
    equity in [-1, 1]) or ``auto`` (weights when all values are in [-1, 1] and some
    are fractional).
    ``extra_checks`` / ``extra`` let wrappers (e.g. grid search) add check
    rows and report sections that take part in the verdict and certificate.
    ``io_watch`` lets a wrapper pass the watch that already covered the strategy
    import (grid search), so data read at import still counts.
    ``jobs`` (a number or ``"auto"``), ``timeout`` (seconds per ``signal()`` call) and
    ``isolate`` (no network, subprocesses or file writes) run a strategy file in worker
    processes; see :mod:`monte_neo.verify.executor`.
    """
    if n_trials is not None and int(n_trials) < 1:
        raise ValueError(f"n_trials must be >= 1 (the chosen variant counts), got {n_trials}")
    if int(min_trades) < 1:
        raise ValueError(f"min_trades must be >= 1, got {min_trades}")
    if not 0.0 < float(holdout_fraction) < 1.0:
        raise ValueError(f"holdout_fraction must be between 0 and 1, got {holdout_fraction}")
    if positions not in POSITION_MODES:
        raise ValueError(f"positions must be one of {POSITION_MODES}, got {positions!r}")
    df = load_ohlcv(ohlcv)
    market = market_for(df)
    n = market.n_bars
    # Every knob that can change the verdict goes into the certificate, so a recheck
    # reruns the same test and a reader sees e.g. a lowered min_trades.
    settings = {
        "min_trades": int(min_trades),
        "holdout_fraction": float(holdout_fraction),
        "probe_checks": int(probe_checks),
        "periods_per_year": float(periods_per_year) if periods_per_year else None,
        "positions": positions,
    }
    if io_watch is None:
        io_watch = IOWatch(tuple(p for p in (df.attrs.get("source_path"),) if p))
    runner = _runner_for(strategy, market, df, jobs, timeout, isolate)
    if runner is not None:
        # Workers load the strategy; this process only reads its source for the lint.
        fn, src = runner, source if source is not None else read_source(runner.path)
    else:
        if (timeout is not None or isolate or resolve_jobs(jobs) > 1) and not isinstance(signal_fn, ProcessRunner):
            raise ValueError("jobs, timeout and isolate need strategy code in a file (strategy='file.py')")
        with io_watch:
            fn, src = _resolve_strategy(strategy, signal_fn, source)
    try:
        return _checks_and_report(
            df, market, fn, src, signals, settings, io_watch, model, n_trials, trial_sharpes,
            periods_per_year, holdout_fraction, min_trades, probe_checks, positions, extra_checks, extra,
        )
    finally:
        if runner is not None:
            runner.close()


def _runner_for(
    strategy: str | Path | None, market: Any, df: pd.DataFrame, jobs: int | str | None, timeout: float | None, isolate: bool
) -> ProcessRunner | None:
    """Worker processes for a strategy file when parallel, time-limited or isolated runs are asked for."""
    n_jobs = resolve_jobs(jobs)
    if strategy is None or (n_jobs == 1 and timeout is None and not isolate):
        return None
    path, func = split_spec(strategy)
    if not path.is_file():
        raise FileNotFoundError(f"strategy file not found: {path}")
    data_paths = tuple(p for p in (df.attrs.get("source_path"),) if p)
    return ProcessRunner(path, func, market.frame, jobs=n_jobs, timeout=timeout, isolate=isolate, data_paths=data_paths)


def _checks_and_report(
    df: pd.DataFrame,
    market: SingleMarket | UniverseMarket,
    fn: Any,
    src: str | None,
    signals: Any,
    settings: dict[str, Any],
    io_watch: IOWatch,
    model: ExecutionModel | None,
    n_trials: int | None,
    trial_sharpes: Any,
    periods_per_year: float | None,
    holdout_fraction: float,
    min_trades: int,
    probe_checks: int,
    positions: str,
    extra_checks: list[dict[str, Any]] | None,
    extra: dict[str, Any] | None,
) -> dict[str, Any]:
    n = market.n_bars
    if fn is None and signals is None:
        raise ValueError("provide signals or strategy code (strategy= / signal_fn=)")
    warn_if_slow(n)
    model = model or _default_model(n)
    if n < model.warmup_bars + 2:
        raise ValueError(f"need at least warmup_bars + 2 = {model.warmup_bars + 2} bars, got {n}")
    ohlc = market.ohlc

    integrity = market.integrity()
    if integrity["status"] == "fail":
        checks = [integrity]
        return _report(checks, {}, market, None, src, model, n_trials, settings)

    with io_watch:
        values = market.read_values(fn, signals)
        # One reading for every probe and backtest: resolved once from the full signal.
        mode = resolve_positions(values, positions)
        settings["positions"] = mode
        full = to_positions(values, mode)  # per row: what the probes compare and the hash covers
        sig, traded = market.positions(values, mode, model)
        determinism = truncation = perturbation = None
        if fn is not None:
            determinism, truncation, perturbation = market.probes(fn, full, mode, probe_checks)
    lint = lint_source(src) if src else None

    run = simulate(ohlc, sig, model)
    rets = bar_returns(run["equity"], start=model.warmup_bars)
    timestamps = market.timestamps
    ppy = float(periods_per_year) if periods_per_year else infer_periods_per_year(timestamps)
    trials = np.asarray(trial_sharpes, dtype=np.float64) if trial_sharpes is not None else None
    dsr = deflated_sharpe(rets, n_trials=int(n_trials or 1), trial_sharpes=trials, periods_per_year=ppy)
    holdout = _holdout(rets, holdout_fraction)
    breakeven = breakeven_cost_bps(ohlc, sig, model)
    delay = delay_scan(ohlc, sig, model)
    timing = timing_significance(ohlc, sig, model) if run["total_return"] > 0.0 else None
    accuracy = market.accuracy(traded)
    total_return = float(run["total_return"])
    n_closed = int(run["n_closed_trades"])
    quality = data_quality(ohlc, timestamps, market.volume)
    profit_share = spike_profit_share(run["equity"], quality["spike_mask"], traded)
    bench = buy_and_hold(ohlc, model, market.benchmark_positions(), ppy)
    by_period = periods(run["equity"], bench["equity"], traded, timestamps, model.warmup_bars, ppy)
    by_regime = regimes(run["equity"], market.market_close(), model.warmup_bars, ppy)

    checks = [
        integrity,
        *market.universe_checks(),
        quality_row(quality, profit_share, market.symbols),
        rows.probe_row("determinism", determinism, "determinism"),
        rows.probe_row("lookahead_truncation", truncation, "truncation probe"),
        rows.probe_row("lookahead_perturbation", perturbation, "future-perturbation probe"),
        rows.external_data_row(*(_outside_data(io_watch, fn) if fn is not None else (None, None))),
        rows.lint_row(lint),
        rows.accuracy_row(accuracy),
        *rows.economics_rows(model, total_return, breakeven, delay),
        rows.timing_row(timing),
        *rows.statistics_rows(dsr, n_closed, int(min_trades), trials_declared=n_trials is not None, holdout=holdout),
        rows.period_row(by_period, total_return),
        rows.benchmark_row(total_return, dsr["sharpe_annualized"], bench),
        *(extra_checks or []),
    ]
    active = np.abs(traded) if traded.ndim == 1 else np.abs(traded).sum(axis=1)
    metrics = {
        "bars": n,
        "total_return": total_return,
        "max_drawdown": float(run["max_drawdown"]),
        "n_fills": int(run["n_trades"]),
        "n_closed_trades": n_closed,
        "positions": mode,
        "exposure": float(np.mean(active != 0)),
        "mean_abs_position": float(np.mean(active)),
        "sharpe_annualized": dsr["sharpe_annualized"],
        "psr": dsr["psr"],
        "deflated_sharpe": dsr["deflated_sharpe"],
        "breakeven_cost_bps": float(breakeven["breakeven_bps"]),
        "hit_rate": accuracy.get("hit_rate"),
        "timing_p_value": timing["p_value"] if timing else None,
        "benchmark_total_return": bench["total_return"],
        "benchmark_sharpe_annualized": bench["sharpe_annualized"],
        **market.describe(traded),
    }
    sections = {
        "benchmark": {
            "description": market.benchmark_description,
            **{k: bench[k] for k in ("total_return", "max_drawdown", "sharpe_annualized")},
        },
        "breakdown": {**by_period, **by_regime},
        "series": series(run["equity"], bench["equity"], timestamps, model.warmup_bars),
        "charts": build_charts(
            run=run, ohlc=ohlc, positions=sig, model=model, timestamps=timestamps, periods_per_year=ppy,
            timing=timing, trades=_trade_journal(ohlc, sig, model, n_closed),
        ),
    }
    return _report(checks, metrics, market, full, src, model, n_trials, settings, extra, sections)


def _trade_journal(ohlc: dict[str, np.ndarray], sig: np.ndarray, model: ExecutionModel, n_closed: int) -> list[dict[str, Any]] | None:
    """Closed trades for the report (sign engine only; skipped for very active strategies, where the journal is slow)."""
    if is_weights(sig) or n_closed == 0 or n_closed > MAX_TRADES_FOR_STATS:
        return None
    return list(run_bar_backtest(ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model)["trades"])


def _outside_data(io_watch: IOWatch, fn: Any) -> tuple[list[str], list[str]]:
    """Data read by the strategy here and, for a runner, in its worker processes."""
    files, conns = list(io_watch.files), list(io_watch.connections)
    if isinstance(fn, ProcessRunner):
        root = fn._owner or fn
        files += [f for f in root.files if f not in files]
        conns += [c for c in root.connections if c not in conns]
    return files, conns


def _report(
    checks: list[dict[str, Any]],
    metrics: dict[str, Any],
    market: SingleMarket | UniverseMarket,
    sig: np.ndarray | None,
    src: str | None,
    model: ExecutionModel,
    n_trials: int | None,
    settings: dict[str, Any],
    extra: dict[str, Any] | None = None,
    sections: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verdict = aggregate_verdict(checks)
    data_bytes = market.data_bytes()
    repro = {
        "engine": "monte-neo",
        "engine_version": __version__,
        "data_sha256": _sha256(data_bytes),
        "signals_sha256": _sha256(np.ascontiguousarray(sig).tobytes()) if sig is not None else None,
        "source_sha256": _sha256(src.encode("utf-8")) if src else None,
        "model": model.to_dict(),
        "n_trials": int(n_trials or 1),
        "settings": settings,
    }
    if market.kind == "universe":
        repro["universe"] = {"symbols": len(market.symbols), "bars": market.n_bars}
    if extra:
        repro["extra_sha256"] = _sha256(json.dumps(to_jsonable(extra), sort_keys=True).encode())
    cert_id = _sha256(json.dumps({"r": repro, "v": verdict}, sort_keys=True, default=str).encode())[:16]
    reasons = [f"{c['id']}: {c['summary']}" for c in checks if c["status"] == "fail"]
    reasons += [f"{c['id']}: {c['summary']}" for c in checks if c["status"] == "warn"]
    return to_jsonable(
        {
            "schema": VERDICT_SCHEMA_ID,
            "verdict": verdict,
            "certificate_id": cert_id,
            "reasons": reasons,
            "checks": checks,
            "metrics": metrics,
            "next_actions": rows.next_actions(checks),
            "reproducibility": repro,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "disclaimer": DISCLAIMER,
            **(sections or {}),  # derived from the hashed inputs: not part of the certificate id
            **(extra or {}),
        }
    )


def model_from_costs(
    *,
    commission_bps: float = 5.0,
    slippage_bps: float = 5.0,
    side_mode: str = "long_short",
    warmup_bars: int | None = None,
    n_bars: int | None = None,
) -> ExecutionModel:
    """Convenience ExecutionModel for CLI / MCP callers."""
    base = _default_model(int(n_bars or 600))
    return replace(
        base,
        commission_bps=float(commission_bps),
        slippage_bps=float(slippage_bps),
        side_mode=side_mode,  # type: ignore[arg-type]
        warmup_bars=int(warmup_bars) if warmup_bars is not None else base.warmup_bars,
    )


__all__ = ["model_from_costs", "verify_strategy"]
