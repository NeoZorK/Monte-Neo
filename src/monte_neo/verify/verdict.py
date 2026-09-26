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
from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify import checks as rows
from monte_neo.verify.costs import breakeven_cost_bps, delay_scan
from monte_neo.verify.ingest import OHLC_COLS, SignalFn, call_signal_fn, load_ohlcv, load_signal_fn, load_signals
from monte_neo.verify.lint import lint_source
from monte_neo.verify.lookahead import (
    implausible_accuracy,
    probe_determinism,
    probe_perturbation,
    probe_truncation,
)
from monte_neo.verify.schema import DISCLAIMER, VERDICT_SCHEMA_ID, aggregate_verdict, to_jsonable
from monte_neo.verify.stats import bar_returns, deflated_sharpe, infer_periods_per_year, sharpe_per_bar


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
    return ExecutionModel(warmup_bars=max(0, min(60, n_bars // 10)))


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
    extra_checks: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify one strategy and return a ``strategy-verdict/1`` report.

    Provide either ``signals`` (positions per bar) or strategy code via
    ``strategy`` (``file.py[:func]``) / ``signal_fn``. Code enables the
    look-ahead probes; ``source`` (or the strategy file) enables static lint.
    ``n_trials`` is how many variants were tried before picking this one.
    ``extra_checks`` / ``extra`` let wrappers (e.g. grid search) add check
    rows and report sections that take part in the verdict and certificate.
    """
    df = load_ohlcv(ohlcv)
    n = len(df)
    fn, src = _resolve_strategy(strategy, signal_fn, source)
    if fn is None and signals is None:
        raise ValueError("provide signals or strategy code (strategy= / signal_fn=)")
    model = model or _default_model(n)
    if n < model.warmup_bars + 2:
        raise ValueError(f"need at least warmup_bars + 2 = {model.warmup_bars + 2} bars, got {n}")
    ohlc = {k: df[k].to_numpy(dtype=np.float64) for k in OHLC_COLS}

    integrity = rows.data_integrity(ohlc)
    if integrity["status"] == "fail":
        checks = [integrity]
        return _report(checks, {}, df, None, src, model, n_trials)

    sig = call_signal_fn(fn, df) if fn is not None else load_signals(signals, n)
    determinism = truncation = perturbation = None
    if fn is not None:
        determinism = probe_determinism(fn, df, full=sig)
        truncation = probe_truncation(fn, df, n_checks=probe_checks, full=sig)
        perturbation = probe_perturbation(fn, df, n_checks=max(2, probe_checks // 4), full=sig)
    lint = lint_source(src) if src else None

    run = run_bar_backtest(ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model)
    rets = bar_returns(run["equity"], start=model.warmup_bars)
    ppy = float(periods_per_year) if periods_per_year else infer_periods_per_year(df.get("timestamp"))
    trials = np.asarray(trial_sharpes, dtype=np.float64) if trial_sharpes is not None else None
    dsr = deflated_sharpe(rets, n_trials=int(n_trials or 1), trial_sharpes=trials, periods_per_year=ppy)
    holdout = _holdout(rets, holdout_fraction)
    breakeven = breakeven_cost_bps(ohlc, sig, model)
    delay = delay_scan(ohlc, sig, model)
    accuracy = implausible_accuracy(ohlc["open"], ohlc["close"], sig)
    total_return = float(run["total_return"])
    n_closed = int(run["n_closed_trades"])

    checks = [
        integrity,
        rows.probe_row("determinism", determinism, "determinism"),
        rows.probe_row("lookahead_truncation", truncation, "truncation probe"),
        rows.probe_row("lookahead_perturbation", perturbation, "future-perturbation probe"),
        rows.lint_row(lint),
        rows.accuracy_row(accuracy),
        *rows.economics_rows(model, total_return, breakeven, delay),
        *rows.statistics_rows(dsr, n_closed, int(min_trades), trials_declared=n_trials is not None, holdout=holdout),
        *(extra_checks or []),
    ]
    metrics = {
        "bars": n,
        "total_return": total_return,
        "max_drawdown": float(run["max_drawdown"]),
        "n_fills": int(run["n_trades"]),
        "n_closed_trades": n_closed,
        "exposure": float(np.mean(sig != 0)),
        "sharpe_annualized": dsr["sharpe_annualized"],
        "psr": dsr["psr"],
        "deflated_sharpe": dsr["deflated_sharpe"],
        "breakeven_cost_bps": float(breakeven["breakeven_bps"]),
        "hit_rate": accuracy.get("hit_rate"),
    }
    return _report(checks, metrics, df, sig, src, model, n_trials, extra)


def _report(
    checks: list[dict[str, Any]],
    metrics: dict[str, Any],
    df: pd.DataFrame,
    sig: np.ndarray | None,
    src: str | None,
    model: ExecutionModel,
    n_trials: int | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verdict = aggregate_verdict(checks)
    data_bytes = np.ascontiguousarray(df[list(OHLC_COLS)].to_numpy(dtype=np.float64)).tobytes()
    repro = {
        "engine": "monte-neo",
        "engine_version": __version__,
        "data_sha256": _sha256(data_bytes),
        "signals_sha256": _sha256(np.ascontiguousarray(sig).tobytes()) if sig is not None else None,
        "source_sha256": _sha256(src.encode("utf-8")) if src else None,
        "model": model.to_dict(),
        "n_trials": int(n_trials or 1),
    }
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
            **(extra or {}),
        }
    )


def model_from_costs(
    *,
    commission_bps: float = 5.0,
    slippage_bps: float = 5.0,
    side_mode: str = "long_flat",
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
