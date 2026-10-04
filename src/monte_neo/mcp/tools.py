"""Agent-facing verifier tools (plain functions; the MCP server only registers them).

Every tool takes file paths (what coding agents already have on disk) and
returns strict-JSON dictionaries.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from monte_neo._version import __version__

SERVER_INSTRUCTIONS = (
    "Monte-Neo is an independent verifier for trading-strategy backtests. "
    "Before you claim a strategy is profitable, call verify_strategy with the OHLCV file and either "
    "the positions file or the strategy .py file (a signal(df) function). Pass n_trials = how many "
    "variants you tried, or call verify_grid with your parameter grid so the verifier counts them. "
    "Treat REJECT as a bug in the backtest, fix what next_actions says and re-verify. "
    "Report the verdict and certificate_id to the user instead of your own backtest numbers. "
    "If you already have numbers you plan to report, pass them as claim (sharpe, total_return, max_drawdown, "
    "n_trades): a claim better than the verified result fails the claim_consistency check. "
    "For intraday strategies on bid/ask quotes call verify_quotes: it checks whether the profit survives the "
    "time the quotes really arrived (stamp + latency)."
)


def _model(
    ohlcv_path: str, commission_bps: float, slippage_bps: float, side_mode: str | None, warmup_bars: int | None,
    signals_path: str | None, funding_bps_per_bar: float = 0.0, borrow_bps_per_bar: float = 0.0,
    sl_pct: float = 0.0, tp_pct: float = 0.0, trail_pct: float = 0.0,
) -> tuple[Any, Any]:
    from monte_neo.verify import load_ohlcv, load_signals, model_from_costs
    from monte_neo.verify.market import bar_count

    df = load_ohlcv(ohlcv_path)
    if side_mode is None:
        has_short = signals_path is not None and bool((load_signals(signals_path) < 0).any())
        side_mode = "long_short" if (has_short or signals_path is None) else "long_flat"
    model = model_from_costs(
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        side_mode=side_mode,
        warmup_bars=warmup_bars,
        n_bars=bar_count(df),
        funding_bps_per_bar=funding_bps_per_bar,
        borrow_bps_per_bar=borrow_bps_per_bar,
        sl_pct=sl_pct,
        tp_pct=tp_pct,
        trail_pct=trail_pct,
    )
    return df, model


def _strategy(strategy_path: str, df: Any, market: Any, timeout: float | None, jobs: int, isolate: bool) -> tuple[Any, str, Any]:
    """(signal function or worker runner, source text, runner to close or None)."""
    from monte_neo.verify.ingest import load_signal_fn
    from monte_neo.verify.limits import read_source
    from monte_neo.verify.verdict import _runner_for

    runner = _runner_for(strategy_path, market, df, jobs, timeout, isolate)
    if runner is not None:
        return runner, read_source(runner.path), runner
    fn, source = load_signal_fn(strategy_path)
    return fn, source, None


def _compact(report: dict[str, Any]) -> dict[str, Any]:
    """Keep details only for failing / warning checks and drop chart series (saves agent context)."""
    out = dict(report)
    out.pop("series", None)
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
    positions: str = "auto",
    timeout: float = 300.0,
    jobs: int = 1,
    isolate: bool = False,
    claim: dict[str, Any] | str | None = None,
    funding_bps_per_bar: float = 0.0,
    borrow_bps_per_bar: float = 0.0,
    sl_pct: float = 0.0,
    tp_pct: float = 0.0,
    trail_pct: float = 0.0,
    symbol_costs: dict[str, Any] | str | None = None,
    compact: bool = True,
    ledger: bool = False,
) -> dict[str, Any]:
    """Verify a strategy backtest and return a strategy-verdict/1 certificate.

    Args:
        ohlcv_path: CSV/Parquet with open, high, low, close (optional timestamp).
        signals_path: Positions per bar (+1 long, 0 flat, -1 short, or weights in [-1, 1]) as CSV/Parquet/NPY.
        strategy_path: Python file 'path.py[:func]' defining func(df) -> positions.
            Enables look-ahead probes and static lint. Runs with your permissions.
        n_trials: Number of variants tried before choosing this one (selection bias).
        ledger: Count the variants tried on this data in .monte-neo/ledger.jsonl (hash-chained); the larger of the
            count and n_trials deflates the Sharpe. Turn it on when you try several variants.
        commission_bps: Commission per side in basis points.
        slippage_bps: Slippage per side in basis points.
        side_mode: 'long_flat' or 'long_short' (default inferred).
        warmup_bars: Bars skipped before trading (default min(60, n/10)).
        positions: 'sign' (+1/0/-1), 'weight' (fraction of equity in [-1, 1]) or 'auto'
            (weights when all values are in [-1, 1] and some are fractional).
        timeout: Seconds allowed per signal() call; the strategy runs in a worker process.
        jobs: Worker processes for the probe calls (raise for slow strategies).
        isolate: Block network, subprocesses and file writes for the strategy.
        claim: What was claimed, e.g. {"sharpe": 2.1, "total_return": 0.85, "max_drawdown": 0.12,
            "n_trades": 300} (or a JSON file path): a claim better than the verified result fails.
        funding_bps_per_bar: Funding on every open position, bps of its value per bar (default 0).
        borrow_bps_per_bar: Borrow fee on short positions only, bps of their value per bar (default 0).
        sl_pct: Stop-loss in percent of the entry price, tested inside each bar (default 0 = off).
        tp_pct: Take-profit in percent of the entry price (default 0 = off).
        trail_pct: Trailing stop in percent from the best price since entry (default 0 = off).
        symbol_costs: Universes only: costs by symbol, e.g. {"AAA": {"commission_bps": 2, "slippage_bps": 1}, "default": {"slippage_bps": 10}}
            (or a JSON file path). A symbol takes its own values, then "default", then the uniform costs above.
        compact: Drop details of passing checks to keep the response short.
    """
    from monte_neo.verify import verify_strategy as _verify

    if not signals_path and not strategy_path:
        return {"error": "provide signals_path or strategy_path"}
    df, model = _model(
        ohlcv_path, commission_bps, slippage_bps, side_mode, warmup_bars, signals_path, funding_bps_per_bar, borrow_bps_per_bar,
        sl_pct, tp_pct, trail_pct,
    )
    runs = {"timeout": timeout, "jobs": jobs, "isolate": isolate} if strategy_path else {}
    report = _verify(
        df, signals=signals_path, strategy=strategy_path, model=model, n_trials=n_trials, positions=positions, claim=claim,
        symbol_costs=symbol_costs, ledger=ledger or None, **runs
    )
    return _compact(report) if compact else report


def verify_grid(
    ohlcv_path: str,
    strategy_path: str,
    grid: dict[str, list[Any]],
    commission_bps: float = 5.0,
    slippage_bps: float = 5.0,
    side_mode: str | None = None,
    folds: int = 4,
    positions: str = "auto",
    timeout: float = 300.0,
    jobs: int = 1,
    isolate: bool = False,
    claim: dict[str, Any] | str | None = None,
    funding_bps_per_bar: float = 0.0,
    borrow_bps_per_bar: float = 0.0,
    sl_pct: float = 0.0,
    tp_pct: float = 0.0,
    trail_pct: float = 0.0,
    symbol_costs: dict[str, Any] | str | None = None,
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
        positions: 'sign', 'weight' or 'auto' (see verify_strategy).
        timeout: Seconds allowed per signal() call; the strategy runs in worker processes.
        jobs: Worker processes (the grid's combos run in parallel).
        isolate: Block network, subprocesses and file writes for the strategy.
        claim: What was claimed (see verify_strategy); compared with the verified result.
        funding_bps_per_bar: Funding on every open position, bps of its value per bar (default 0).
        borrow_bps_per_bar: Borrow fee on short positions only, bps of their value per bar (default 0).
        sl_pct: Stop-loss in percent of the entry price, tested inside each bar (default 0 = off).
        tp_pct: Take-profit in percent of the entry price (default 0 = off).
        trail_pct: Trailing stop in percent from the best price since entry (default 0 = off).
        symbol_costs: Universes only: costs by symbol, e.g. {"AAA": {"commission_bps": 2, "slippage_bps": 1}, "default": {"slippage_bps": 10}}
            (or a JSON file path). A symbol takes its own values, then "default", then the uniform costs above.
        compact: Drop details of passing checks to keep the response short.
    """
    from monte_neo.verify import verify_grid as _verify_grid

    df, model = _model(
        ohlcv_path, commission_bps, slippage_bps, side_mode, None, None, funding_bps_per_bar, borrow_bps_per_bar, sl_pct, tp_pct, trail_pct
    )
    report = _verify_grid(
        df, grid, strategy=strategy_path, model=model, folds=folds, positions=positions,
        timeout=timeout, jobs=jobs, isolate=isolate, claim=claim, symbol_costs=symbol_costs,
    )
    return _compact(report) if compact else report


def recheck_certificate(
    certificate_path: str,
    ohlcv_path: str | None = None,
    signals_path: str | None = None,
    strategy_path: str | None = None,
    timeout: float = 300.0,
    isolate: bool = False,
    quotes_path: str | None = None,
) -> dict[str, Any]:
    """Reproduce a strategy-verdict/1 certificate from its original inputs.

    Args:
        certificate_path: JSON certificate written by verify (--out) or returned by a tool.
        ohlcv_path: The same OHLCV file that was verified (not for a quote certificate).
        signals_path: The same positions file (or use strategy_path).
        strategy_path: The same strategy file that was verified.
        timeout: Seconds allowed per signal() call; the strategy runs in a worker process.
        isolate: Block network, subprocesses and file writes for the strategy.
        quotes_path: The same quotes file, for a certificate issued by verify_quotes (needs strategy_path).
    """
    from monte_neo.verify import recheck_certificate as _recheck
    from monte_neo.verify import to_jsonable

    if quotes_path:
        from monte_neo.verify.quotes_verdict import recheck_quotes

        if not strategy_path:
            return {"error": "provide strategy_path with quotes_path"}
        return to_jsonable(recheck_quotes(certificate_path, quotes_path, strategy=strategy_path))
    if not ohlcv_path:
        return {"error": "provide ohlcv_path (or quotes_path for a quote certificate)"}
    if not signals_path and not strategy_path:
        return {"error": "provide signals_path or strategy_path"}
    runs = {"timeout": timeout, "isolate": isolate} if strategy_path else {}
    return to_jsonable(_recheck(certificate_path, ohlcv_path, signals=signals_path, strategy=strategy_path, **runs))


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


def probe_lookahead(
    ohlcv_path: str, strategy_path: str, timeout: float = 300.0, jobs: int = 1, isolate: bool = False
) -> dict[str, Any]:
    """Look-ahead probes only: static lint, outside data, determinism, truncation, future perturbation.

    Args:
        ohlcv_path: CSV/Parquet with open, high, low, close.
        strategy_path: Python file 'path.py[:func]' defining func(df) -> positions.
        timeout: Seconds allowed per signal() call; the strategy runs in a worker process.
        jobs: Worker processes for the probe calls.
        isolate: Block network, subprocesses and file writes for the strategy.
    """
    from monte_neo.verify import lint_source, load_ohlcv, resolve_positions, to_jsonable, to_positions
    from monte_neo.verify.io_guard import IOWatch
    from monte_neo.verify.market import market_for

    df = load_ohlcv(ohlcv_path)
    market = market_for(df)  # one instrument, or a universe probed across all symbols at once
    watch = IOWatch((df.attrs["source_path"],))
    runner = None
    try:
        with watch:
            fn, source, runner = _strategy(strategy_path, df, market, timeout, jobs, isolate)
            values = market.read_values(fn, None)
            mode = resolve_positions(values, "auto")
            determinism, truncation, perturbation = market.probes(fn, to_positions(values, mode), mode, 24)
    finally:
        if runner is not None:
            runner.close()
    for name in runner.files if runner is not None else []:
        if name not in watch.files:
            watch.files.append(name)
    for host in runner.connections if runner is not None else []:
        if host not in watch.connections:
            watch.connections.append(host)
    report: dict[str, Any] = {
        "static_lint": lint_source(source),
        "determinism": determinism,
        "truncation": truncation,
        "perturbation": perturbation,
    }
    outside = bool(watch.files or watch.connections)
    report["external_data"] = {
        "status": "fail" if outside else "pass", "files": watch.files, "connections": watch.connections,
    }
    report["leak_detected"] = any(
        report[k]["status"] == "fail" for k in ("static_lint", "external_data", "truncation", "perturbation")
    )
    return to_jsonable(report)


def cost_stress(
    ohlcv_path: str,
    signals_path: str | None = None,
    strategy_path: str | None = None,
    commission_bps: float = 5.0,
    slippage_bps: float = 5.0,
    side_mode: str | None = None,
    positions: str = "auto",
    timeout: float = 300.0,
) -> dict[str, Any]:
    """Break-even cost (bps per side) and returns under 0/1/2 bars of execution delay.

    Args:
        ohlcv_path: CSV/Parquet with open, high, low, close.
        signals_path: Positions per bar file (or use strategy_path).
        strategy_path: Python file 'path.py[:func]' defining func(df) -> positions.
        commission_bps: Commission per side in basis points.
        slippage_bps: Slippage per side in basis points.
        side_mode: 'long_flat' or 'long_short' (default inferred).
        positions: 'sign', 'weight' or 'auto' (see verify_strategy).
        timeout: Seconds allowed for the signal() call; the strategy runs in a worker process.
    """
    from monte_neo.verify import breakeven_cost_bps, delay_scan, resolve_positions, to_jsonable
    from monte_neo.verify.market import market_for

    if not signals_path and not strategy_path:
        return {"error": "provide signals_path or strategy_path"}
    df, model = _model(ohlcv_path, commission_bps, slippage_bps, side_mode, None, signals_path)
    market = market_for(df)
    fn, runner = None, None
    try:
        if strategy_path:
            fn, _, runner = _strategy(strategy_path, df, market, timeout, 1, False)
        values = market.read_values(fn, signals_path)
    except ValueError as exc:
        return {"error": str(exc)}
    finally:
        if runner is not None:
            runner.close()
    sig = market.positions(values, resolve_positions(values, positions), model)[0]
    return to_jsonable({"breakeven": breakeven_cost_bps(market.ohlc, sig, model), "delay": delay_scan(market.ohlc, sig, model)})


def render_report(certificate_path: str, html_path: str) -> dict[str, Any]:
    """Write a certificate as a self-contained HTML report for people (equity chart, checks, periods).

    Args:
        certificate_path: JSON certificate written by verify (--out) or saved from verify_strategy.
        html_path: Where to write the .html file.
    """
    from pathlib import Path

    from monte_neo.verify.recheck import load_certificate
    from monte_neo.verify.report_html import write_html

    if Path(html_path).suffix.lower() not in (".html", ".htm"):
        # An agent acting on injected instructions must not be able to overwrite arbitrary files.
        return {"error": f"html_path must end with .html or .htm, got {Path(html_path).name!r}"}
    try:
        path = write_html(load_certificate(certificate_path), html_path)
    except Exception as exc:  # unreadable or not a certificate: report, do not crash the server
        return {"error": str(exc)}
    return {"html_path": str(path), "bytes": path.stat().st_size}


def verify_quotes(
    quotes_path: str,
    strategy_path: str,
    bar_ms: float = 1000.0,
    commission_bps: float = 1.0,
    slippage_bps: float = 0.0,
    latency_samples: int = 200,
    positions: str = "auto",
    compact: bool = True,
    symbol: str | None = None,
    order_latency_ms: float = 0.0,
    feeds: list[str] | None = None,
    latency_model: str | None = None,
    probes: bool = True,
) -> dict[str, Any]:
    """Verify a strategy against the time its quotes really arrived; returns a strategy-verdict/1 certificate.

    Use this for intraday strategies built on bid/ask quotes. A backtest that bins quotes by the exchange
    stamp lets the strategy act on prices that had not reached you yet; this tool also bins them by
    stamp + latency and compares.

    Args:
        quotes_path: CSV/Parquet of one instrument with timestamp, bid, ask and latency_ms (or an arrival timestamp).
        strategy_path: Python file 'path.py[:func]' defining func(df) -> positions on bars of open, high, low,
            close, volume. Runs with your permissions.
        bar_ms: Bar length in milliseconds.
        commission_bps: Commission per side in basis points (default 1: quote strategies trade often).
        slippage_bps: Slippage per side in basis points.
        latency_samples: Seeded redraws of the observed latency for the Monte Carlo.
        positions: 'sign', 'weight' or 'auto'.
        compact: Drop details of passing checks to keep the response short.
        symbol: The symbol to verify when the table holds several.
        order_latency_ms: Delay from the decision to the fill in ms (the data latency comes from the quotes).
        feeds: Other symbols the strategy reads (needs symbol); their columns are prefixed by the symbol with
            non-word characters replaced by "_", e.g. ETH_USDT_X_close.
        latency_model: Assume the data latency instead of reading it: "constant:MS" or "lognormal:MEDIAN_MS,P95_MS".
        probes: Also run the look-ahead probes of verify_strategy on the arrival bars.
    """
    from monte_neo.verify.quotes_verdict import verify_quotes as _verify

    report = _verify(
        quotes_path, strategy=strategy_path, bar_ms=bar_ms, commission_bps=commission_bps, slippage_bps=slippage_bps,
        samples=latency_samples, positions=positions, symbol=symbol, order_latency_ms=order_latency_ms,
        feeds=feeds, latency_model=latency_model, probes=probes,
    )
    return _compact(report) if compact else report


def suggest_fix(strategy_path: str) -> dict[str, Any]:
    """Suggest a causal rewrite of a strategy file that reads the future (negative shifts, centred windows, whole-table statistics...).

    Returns the rewrites (rule, line, before, after), the patched source, a unified diff and the lint findings that
    remain. The patch keeps the shape of the strategy, not its meaning: verify it with verify_strategy before using it,
    and write the patched source to a new file yourself (nothing is written here). Comments are not kept.
    """
    from monte_neo.verify.fixes import suggest_fixes

    path = Path(strategy_path.split(":")[0])
    if not path.is_file():
        raise FileNotFoundError(f"strategy file not found: {path}")
    return suggest_fixes(path.read_text(encoding="utf-8"))


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
            "positions": (
                "signs (+1 long, 0 flat, -1 short; any number is reduced to its sign) or weights "
                "(fraction of equity in [-1, 1], e.g. 0.5 = long half); 'auto' reads weights when all values "
                "are in [-1, 1] and some are fractional; NaN = flat"
            ),
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
    render_report,
    verify_quotes,
    suggest_fix,
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
    "render_report",
    "suggest_fix",
    "verdict_schema",
    "verifier_manifest",
    "verify_grid",
    "verify_quotes",
    "verify_strategy",
]
