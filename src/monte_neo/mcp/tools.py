"""Agent-facing verifier tools (plain functions; the MCP server only registers them).

Every tool takes file paths (what coding agents already have on disk) and
returns strict-JSON dictionaries.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from monte_neo._version import __version__

SERVER_INSTRUCTIONS = (
    "Monte-Neo is an independent verifier for trading-strategy backtests. "
    "Before you claim a strategy is profitable, call verify_strategy with the OHLCV file and either "
    "the positions file or the strategy .py file (a signal(df) function). Pass n_trials = how many "
    "variants you tried, or call verify_grid with your parameter grid so the verifier counts them. "
    "Treat REJECT as a bug in the backtest, fix what next_actions says and re-verify. "
    "Report the verdict and certificate_id to the user instead of your own backtest numbers."
)


def _model(ohlcv_path: str, commission_bps: float, slippage_bps: float, side_mode: str | None, warmup_bars: int | None, signals_path: str | None) -> tuple[Any, Any]:
    from monte_neo.verify import load_ohlcv, load_signals, model_from_costs

    df = load_ohlcv(ohlcv_path)
    if side_mode is None:
        has_short = signals_path is not None and bool((load_signals(signals_path) < 0).any())
        side_mode = "long_short" if (has_short or signals_path is None) else "long_flat"
    model = model_from_costs(
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        side_mode=side_mode,
        warmup_bars=warmup_bars,
        n_bars=len(df),
    )
    return df, model


def _compact(report: dict[str, Any]) -> dict[str, Any]:
    """Keep details only for failing / warning checks (saves agent context)."""
    out = dict(report)
    out["checks"] = [
        c if c["status"] in ("fail", "warn") else {k: v for k, v in c.items() if k != "details"}
        for c in report["checks"]
    ]
    return out


def verify_strategy(
    ohlcv_path: str,
    signals_path: str | None = None,
    strategy_path: str | None = None,
    n_trials: int | None = None,
    commission_bps: float = 5.0,
    slippage_bps: float = 5.0,
    side_mode: str | None = None,
    warmup_bars: int | None = None,
    compact: bool = True,
) -> dict[str, Any]:
    """Verify a strategy backtest and return a strategy-verdict/1 certificate.

    Args:
        ohlcv_path: CSV/Parquet with open, high, low, close (optional timestamp).
        signals_path: Positions per bar (+1 long, 0 flat, -1 short) as CSV/Parquet/NPY.
        strategy_path: Python file 'path.py[:func]' defining func(df) -> positions.
            Enables look-ahead probes and static lint. Runs with your permissions.
        n_trials: Number of variants tried before choosing this one (selection bias).
        commission_bps: Commission per side in basis points.
        slippage_bps: Slippage per side in basis points.
        side_mode: 'long_flat' or 'long_short' (default inferred).
        warmup_bars: Bars skipped before trading (default min(60, n/10)).
        compact: Drop details of passing checks to keep the response short.
    """
    from monte_neo.verify import verify_strategy as _verify

    if not signals_path and not strategy_path:
        return {"error": "provide signals_path or strategy_path"}
    df, model = _model(ohlcv_path, commission_bps, slippage_bps, side_mode, warmup_bars, signals_path)
    report = _verify(df, signals=signals_path, strategy=strategy_path, model=model, n_trials=n_trials)
    return _compact(report) if compact else report


def verify_grid(
    ohlcv_path: str,
    strategy_path: str,
    grid: dict[str, list[Any]],
    commission_bps: float = 5.0,
    slippage_bps: float = 5.0,
    side_mode: str | None = None,
    folds: int = 4,
    compact: bool = True,
) -> dict[str, Any]:
    """Run the parameter search inside the verifier and verify the best combo.

    Prefer this over verify_strategy when you tuned parameters: n_trials and the
    spread of trial Sharpes are measured instead of declared, and an anchored
    walk-forward scores re-selected parameters out of sample.

    Args:
        ohlcv_path: CSV/Parquet with open, high, low, close.
        strategy_path: Python file 'path.py[:func]' defining func(df, **params) -> positions.
        grid: Parameter grid, e.g. {"fast": [10, 20], "slow": [50, 100]} (max 512 combos).
        commission_bps: Commission per side in basis points.
        slippage_bps: Slippage per side in basis points.
        side_mode: 'long_flat' or 'long_short' (default long_short).
        folds: Walk-forward folds.
        compact: Drop details of passing checks to keep the response short.
    """
    from monte_neo.verify import verify_grid as _verify_grid

    df, model = _model(ohlcv_path, commission_bps, slippage_bps, side_mode, None, None)
    report = _verify_grid(df, grid, strategy=strategy_path, model=model, folds=folds)
    return _compact(report) if compact else report


def recheck_certificate(
    certificate_path: str,
    ohlcv_path: str,
    signals_path: str | None = None,
    strategy_path: str | None = None,
) -> dict[str, Any]:
    """Reproduce a strategy-verdict/1 certificate from its original inputs.

    Args:
        certificate_path: JSON certificate written by verify (--out) or returned by a tool.
        ohlcv_path: The same OHLCV file that was verified.
        signals_path: The same positions file (or use strategy_path).
        strategy_path: The same strategy file that was verified.
    """
    from monte_neo.verify import recheck_certificate as _recheck
    from monte_neo.verify import to_jsonable

    if not signals_path and not strategy_path:
        return {"error": "provide signals_path or strategy_path"}
    return to_jsonable(_recheck(certificate_path, ohlcv_path, signals=signals_path, strategy=strategy_path))


def check_signature(certificate_path: str, public_key: str | None = None) -> dict[str, Any]:
    """Check the Ed25519 signature of a strategy-verdict/1 certificate.

    Args:
        certificate_path: Signed JSON certificate.
        public_key: The issuer's published key ('ed25519:<base64>' or a .pub file). Without it
            the check proves only that the certificate was not edited after signing.
    """
    from monte_neo.verify.signing import check_signature as _check

    try:
        return _check(certificate_path, public_key=public_key)
    except Exception as exc:  # missing extra or unreadable file: report, do not crash the server
        return {"error": str(exc)}


def probe_lookahead(ohlcv_path: str, strategy_path: str) -> dict[str, Any]:
    """Look-ahead probes only: static lint, determinism, truncation, future perturbation.

    Args:
        ohlcv_path: CSV/Parquet with open, high, low, close.
        strategy_path: Python file 'path.py[:func]' defining func(df) -> positions.
    """
    from monte_neo.verify import (
        call_signal_fn,
        lint_source,
        load_ohlcv,
        load_signal_fn,
        probe_determinism,
        probe_perturbation,
        probe_truncation,
        to_jsonable,
    )

    df = load_ohlcv(ohlcv_path)
    fn, source = load_signal_fn(strategy_path)
    full = call_signal_fn(fn, df)
    report: dict[str, Any] = {
        "static_lint": lint_source(source),
        "determinism": probe_determinism(fn, df, full=full),
        "truncation": probe_truncation(fn, df, full=full),
        "perturbation": probe_perturbation(fn, df, full=full),
    }
    report["leak_detected"] = any(
        report[k]["status"] == "fail" for k in ("static_lint", "truncation", "perturbation")
    )
    return to_jsonable(report)


def cost_stress(
    ohlcv_path: str,
    signals_path: str | None = None,
    strategy_path: str | None = None,
    commission_bps: float = 5.0,
    slippage_bps: float = 5.0,
    side_mode: str | None = None,
) -> dict[str, Any]:
    """Break-even cost (bps per side) and returns under 0/1/2 bars of execution delay.

    Args:
        ohlcv_path: CSV/Parquet with open, high, low, close.
        signals_path: Positions per bar file (or use strategy_path).
        strategy_path: Python file 'path.py[:func]' defining func(df) -> positions.
        commission_bps: Commission per side in basis points.
        slippage_bps: Slippage per side in basis points.
        side_mode: 'long_flat' or 'long_short' (default inferred).
    """
    from monte_neo.verify import (
        breakeven_cost_bps,
        call_signal_fn,
        delay_scan,
        load_signal_fn,
        load_signals,
        to_jsonable,
    )

    if not signals_path and not strategy_path:
        return {"error": "provide signals_path or strategy_path"}
    df, model = _model(ohlcv_path, commission_bps, slippage_bps, side_mode, None, signals_path)
    if strategy_path:
        sig = call_signal_fn(load_signal_fn(strategy_path)[0], df)
    else:
        sig = load_signals(signals_path, len(df))
    ohlc = {k: df[k].to_numpy() for k in ("open", "high", "low", "close")}
    return to_jsonable({"breakeven": breakeven_cost_bps(ohlc, sig, model), "delay": delay_scan(ohlc, sig, model)})


def verdict_schema() -> dict[str, Any]:
    """JSON schema of the strategy-verdict/1 certificate."""
    from monte_neo.verify import VERDICT_JSON_SCHEMA

    return VERDICT_JSON_SCHEMA


def verifier_manifest() -> dict[str, Any]:
    """Execution semantics and check catalogue — read before building a backtest."""
    from monte_neo.verify.checks import NEXT_ACTIONS

    return {
        "engine": "monte-neo",
        "version": __version__,
        "execution": {
            "fill": "signal on bar t fills at open of bar t+1",
            "costs": "commission_bps + slippage_bps per side on fill notional",
            "positions": "+1 long, 0 flat, -1 short; any number is reduced to its sign; NaN = flat",
        },
        "verdicts": {
            "PASS": "no problems found",
            "PASS_WITH_WARNINGS": "usable, read the warnings",
            "NEEDS_MORE_EVIDENCE": "statistics too weak (few trades, Sharpe does not survive n_trials)",
            "REJECT": "backtest is broken or unprofitable after costs (look-ahead, bad data, losses)",
        },
        "checks": {k: v for k, v in NEXT_ACTIONS.items()},
        "instructions": SERVER_INSTRUCTIONS,
    }


TOOLS: tuple[Callable[..., dict[str, Any]], ...] = (
    verify_strategy,
    verify_grid,
    recheck_certificate,
    check_signature,
    probe_lookahead,
    cost_stress,
    verdict_schema,
    verifier_manifest,
)

__all__ = [
    "SERVER_INSTRUCTIONS",
    "recheck_certificate",
    "TOOLS",
    "check_signature",
    "cost_stress",
    "probe_lookahead",
    "verdict_schema",
    "verifier_manifest",
    "verify_grid",
    "verify_strategy",
]
