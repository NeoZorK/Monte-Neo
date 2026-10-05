"""``monte-neo verify`` — CI-friendly strategy verifier command.

Exit codes: 0 PASS / PASS_WITH_WARNINGS, 1 NEEDS_MORE_EVIDENCE, 2 REJECT,
3 usage or input error, 4 certificate not reproduced (``--recheck``),
5 signature invalid or signed by an unexpected key (``--check-signature``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

EXIT_CODES = {"PASS": 0, "PASS_WITH_WARNINGS": 0, "NEEDS_MORE_EVIDENCE": 1, "REJECT": 2}
_STATUS_STYLE = {"pass": "green", "warn": "yellow", "fail": "bold red", "skip": "dim", "info": "cyan"}
_VERDICT_STYLE = {"PASS": "bold green", "PASS_WITH_WARNINGS": "bold yellow", "NEEDS_MORE_EVIDENCE": "bold magenta", "REJECT": "bold red"}


def build_parser() -> argparse.ArgumentParser:
    """Argument parser for ``monte-neo verify``."""
    p = argparse.ArgumentParser(
        prog="monte-neo verify",
        description="Verify a trading strategy backtest: look-ahead, costs, selection bias.",
    )
    p.add_argument("--ohlcv", help="OHLCV table (.csv / .parquet) with open, high, low, close[, timestamp]")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--signals", help="Positions per bar (.csv / .parquet / .npy): +1 long, 0 flat, -1 short, or weights in [-1, 1]")
    src.add_argument("--strategy", help="Strategy file 'path.py[:func]' with func(df) -> positions (default func: signal)")
    p.add_argument("--quotes", help="Quotes table (.csv / .parquet) with timestamp, bid, ask and latency_ms (or arrival): checks the strategy against the time data arrived (needs --strategy)")
    p.add_argument("--bar-ms", type=float, default=1000.0, help="Bar length in milliseconds for --quotes (default 1000)")
    p.add_argument("--symbol", help="Symbol to verify when the --quotes table holds several (the quotes of one instrument are verified)")
    p.add_argument("--feeds", help="Other symbols the strategy reads, comma separated (columns <alias>_open ... <alias>_volume; needs --symbol)")
    p.add_argument("--latency-model", help="Assume the data latency instead of reading it: constant:MS or lognormal:MEDIAN_MS,P95_MS (the quotes may have no latency column)")
    p.add_argument("--no-probes", action="store_true", help="Skip the look-ahead probes that run on the arrival bars with --quotes")
    p.add_argument("--order-latency-ms", type=float, default=0.0, help="Delay from the decision to the fill in ms for --quotes (default 0: only the data latency counts)")
    p.add_argument("--latency-samples", type=int, default=200, help="Latency draws for the --quotes Monte Carlo (default 200)")
    p.add_argument("--n-trials", type=int, default=None, help="How many variants were tried before this one")
    p.add_argument(
        "--ledger", nargs="?", const="1", default=None, metavar="PATH",
        help="Count the variants tried on this data in an append-only ledger (default .monte-neo/ledger.jsonl); the larger of the count and --n-trials is used",
    )
    p.add_argument("--registration", metavar="ID", help="id of a pre-registered hypothesis (monte-neo register): the certificate says whether it protects this result")
    p.add_argument("--repaint", choices=["off", "auto", "strict"], default="auto", help="How densely to check that a signal never changes after it was shown (default auto; strict checks many more prefixes)")
    p.add_argument("--signal-timing", choices=["close", "open"], default="close", help="'open': the signal is declared known at the bar's open, so a signal that needs the bar's own prices fails (default close)")
    p.add_argument("--grid", help="Parameter grid as JSON or a .json file, e.g. '{\"fast\": [10, 20], \"slow\": [50, 100]}' (needs --strategy)")
    p.add_argument("--folds", type=int, default=4, help="Walk-forward folds for --grid (default 4)")
    p.add_argument("--commission-bps", type=float, default=5.0, help="Commission per side in bps (default 5)")
    p.add_argument("--slippage-bps", type=float, default=5.0, help="Slippage per side in bps (default 5)")
    p.add_argument(
        "--positions", choices=["auto", "sign", "weight"], default="auto",
        help="Read signals as signs (+1/0/-1), as weights (fraction of equity in [-1, 1]) or auto (default: weights when all values are in [-1, 1] and some are fractional)",
    )
    p.add_argument(
        "--claim", help="What was claimed, as a JSON file or text, e.g. '{\"sharpe\": 2.1, \"total_return\": 0.85}': an overclaim fails the check",
    )
    p.add_argument("--funding-bps-per-bar", type=float, default=0.0, help="Funding charged on every open position, bps of its value per bar (default 0)")
    p.add_argument("--borrow-bps-per-bar", type=float, default=0.0, help="Borrow fee charged on short positions only, bps of their value per bar (default 0)")
    p.add_argument("--costs-file", metavar="PATH_OR_JSON", help='Per-symbol costs for a universe: a JSON file or text, {"AAA": {"commission_bps": 2, "slippage_bps": 1}, "default": {...}}')
    p.add_argument("--sl-pct", type=float, default=0.0, help="Stop-loss in percent of the entry price, tested inside each bar (default off)")
    p.add_argument("--tp-pct", type=float, default=0.0, help="Take-profit in percent of the entry price (default off)")
    p.add_argument("--trail-pct", type=float, default=0.0, help="Trailing stop in percent from the best price since entry (default off)")
    p.add_argument("--side-mode", choices=["long_flat", "long_short"], default=None, help="Default: long_short if signals contain shorts")
    p.add_argument("--warmup-bars", type=int, default=None, help="Bars ignored before trading (default min(60, n/10))")
    p.add_argument("--periods-per-year", type=float, default=None, help="Bars per year for annualization (default: inferred)")
    p.add_argument(
        "--jobs", default="1",
        help="Worker processes for the strategy's probe calls: a number or 'auto' (default 1: run in this process)",
    )
    p.add_argument("--timeout", type=float, default=None, help="Seconds allowed per signal() call (runs the strategy in a worker)")
    p.add_argument(
        "--isolate", action="store_true",
        help="Run the strategy in a worker without network, subprocesses, file writes or secrets in the environment",
    )
    p.add_argument("--min-trades", type=int, default=30, help="Minimum closed trades for statistics (default 30)")
    p.add_argument("--out", help="Write the strategy-verdict/1 JSON certificate to this path")
    p.add_argument("--html", help="Also write a self-contained HTML report (charts, checks, periods) to this path")
    p.add_argument("--badge", metavar="PATH", help="Also write a shields.io endpoint JSON (verdict + certificate id) for a README badge")
    p.add_argument("--lint", nargs="+", metavar="FILE", help="Only run the static look-ahead lint on these strategy files and exit (for pre-commit)")
    p.add_argument("--suggest-fix", metavar="FILE", help="Print a causal rewrite of a strategy file that reads the future (a diff; nothing is written) and exit")
    p.add_argument("--render", metavar="CERT", help="Render an existing certificate JSON as HTML (needs --html) and exit")
    p.add_argument("--recheck", help="Reproduce this certificate JSON from --ohlcv and --signals / --strategy")
    p.add_argument("--sign", metavar="KEY", help="Sign the certificate with this Ed25519 private key (PEM); needs monte-neo[sign]")
    p.add_argument("--keygen", metavar="PREFIX", help="Create PREFIX.key (private) and PREFIX.pub (public) and exit")
    p.add_argument("--check-signature", metavar="CERT", help="Check the signature of this certificate JSON and exit")
    p.add_argument("--public-key", help="Expected signer for --check-signature: 'ed25519:<base64>' or a .pub file")
    p.add_argument("--format", choices=["text", "json"], default="text", help="stdout format (default text)")
    p.add_argument("--schema", action="store_true", help="Print the strategy-verdict/1 JSON schema and exit")
    p.add_argument("--demo-quotes", action="store_true", help="Try the arrival-time checks with no files: a strategy that needs data before it arrived, and an honest one")
    p.add_argument("--demo", action="store_true", help="Try it with no files: verify a leaky and an honest built-in strategy on synthetic data")
    p.add_argument(
        "--precompile", action="store_true",
        help="Compile and cache the backtest engines (about 5 s once), e.g. when building a Docker image, and exit",
    )
    return p


_VERDICT_MEANING = {
    "PASS": "no problem found in the backtest",
    "PASS_WITH_WARNINGS": "usable, read the warnings",
    "NEEDS_MORE_EVIDENCE": "not enough evidence to trust the result yet",
    "REJECT": "do not trust this backtest",
}


def _render_summary(report: dict[str, Any], console: Console, with_next: bool = True) -> None:
    """Plain-language answer under the table: what the verdict means, the first reason and the first step."""
    verdict = report["verdict"]
    console.print(f"[bold]In short:[/] {verdict}, {_VERDICT_MEANING.get(verdict, '')}")
    reasons = report.get("reasons") or []
    if reasons:
        console.print(f"[bold]Why:[/] {reasons[0]}" + (f" (+{len(reasons) - 1} more)" if len(reasons) > 1 else ""))
    actions = report.get("next_actions") or []
    if with_next and actions:
        console.print(f"[bold]Next:[/] {actions[0]}")


def _run_demo(console: Console) -> int:
    """Verify a strategy that reads tomorrow's close and an honest moving-average one, on synthetic prices."""
    import numpy as np

    from monte_neo.backtest import synthetic_ohlcv
    from monte_neo.verify import verify_strategy

    def leaky(df):
        return np.sign(df["close"].shift(-1) - df["close"]).to_numpy()  # tomorrow's close decides today's position

    def honest(df):
        return np.where(df["close"].rolling(20).mean() > df["close"].rolling(80).mean(), 1, 0)  # rows <= t only

    df = synthetic_ohlcv(3000, seed=1)
    console.print("[bold]Demo:[/] two strategies on 3000 synthetic bars. The first one peeks at tomorrow's close.\n")
    for name, fn, src in (
        ("leaky (uses shift(-1))", leaky, "x = df['close'].shift(-1)"),
        ("no-peeking (moving-average crossover)", honest, None),
    ):
        report = verify_strategy(df, signal_fn=fn, source=src, n_trials=10)
        console.print(f"[bold]{name}[/]")
        console.print(f"[{_VERDICT_STYLE[report['verdict']]}]{report['verdict']}[/]  certificate {report['certificate_id']}")
        leaks = [c for c in report["checks"] if c["category"] == "lookahead" and c["status"] == "fail"]
        console.print("Look-ahead checks: " + ("[red]leak found[/]" if leaks else "[green]clean, no future data used[/]"))
        _render_summary(report, console)
        console.print()
    console.print(
        "Prices here are random, so a strategy that does not cheat has no edge either: "
        "Monte-Neo separates 'the backtest lies' from 'the strategy does not earn'."
    )
    console.print("Now try your own: [bold]monte-neo verify --ohlcv data.csv --strategy my_strategy.py[/]")
    return 0


def _render_text(report: dict[str, Any], console: Console) -> None:
    verdict = report["verdict"]
    console.print(f"[{_VERDICT_STYLE[verdict]}]{verdict}[/]  certificate {report['certificate_id']}")
    table = Table(show_header=True, header_style="bold")
    for col in ("check", "category", "status", "summary"):
        table.add_column(col)
    for c in report["checks"]:
        style = _STATUS_STYLE.get(c["status"], "")
        table.add_row(c["id"], c["category"], f"[{style}]{c['status']}[/]", c["summary"])
    console.print(table)
    _render_summary(report, console, with_next=False)
    if report.get("ledger"):
        led = report["ledger"]
        note = "" if led["chain_ok"] else " [red](the ledger was changed)[/]"
        console.print(f"[bold]Ledger:[/] {led['variants_counted']} variant(s) tried on this data, n_trials {led['n_trials_used']}{note}")
    grid = report.get("grid")
    if grid:
        wf = grid["walk_forward"]
        console.print(
            f"grid: {grid['n_combos']} combos · best {grid['best_params']} · walk-forward OOS Sharpe/bar"
            f" {wf['oos_sharpe']:+.4f} · stability {wf['param_stability']:.2f}"
        )
    m = report.get("metrics") or {}
    if "latency_p50_ms" in m:  # a quote certificate (verify --quotes)
        console.print(
            f"exchange clock {m['return_exchange_clock']:+.2%} · arrival clock {m['return_arrival_clock']:+.2%}"
            f" · latency p50 {m['latency_p50_ms']:.0f} ms, p95 {m['latency_p95_ms']:.0f} ms · bars {m['bar_ms']:g} ms"
        )
    elif m:
        console.print(
            f"return {m['total_return']:+.2%} · maxDD {m['max_drawdown']:.2%} · trades {m['n_closed_trades']}"
            f" · Sharpe(ann) {m['sharpe_annualized']:.2f} · DSR {m['deflated_sharpe']:.3f}"
            f" · break-even {m['breakeven_cost_bps']:.1f} bps"
        )
    for note in report.get("assumptions") or []:  # a quote certificate: what the run does and does not model
        console.print(f"[dim]assumes: {note}[/]")
    by_period = (report.get("breakdown") or {}).get("periods") or []
    if by_period:
        console.print("periods: " + " · ".join(f"{p['period']} {p['return']:+.1%}" for p in by_period[:12]))
    for action in report["next_actions"]:
        console.print(f"[yellow]→ {action}[/]")
    console.print(f"[dim]{report['disclaimer']}[/]")


def _load_grid(spec: str) -> dict[str, list[Any]]:
    from monte_neo.verify.limits import MAX_GRID_BYTES, loads_strict, read_text_limited

    text = read_text_limited(spec, MAX_GRID_BYTES, "grid") if spec.endswith(".json") and Path(spec).is_file() else spec
    grid = loads_strict(text)
    if not isinstance(grid, dict):
        raise ValueError("--grid must be a JSON object {name: [values]}")
    return grid


def _side_mode(args: argparse.Namespace) -> str:
    if args.side_mode:
        return str(args.side_mode)
    if args.signals:
        from monte_neo.verify.ingest import load_signals

        return "long_short" if (load_signals(args.signals) < 0).any() else "long_flat"
    return "long_short"


def _run_signing(args: argparse.Namespace, console: Console) -> int:
    from monte_neo.verify.signing import check_signature, generate_keypair, signature_ok

    try:
        if args.keygen:
            keys = generate_keypair(args.keygen)
            console.print(f"private key {keys['private_key']} (keep secret) · public key {keys['public_key']} · key id {keys['key_id']}")
            return 0
        result = check_signature(args.check_signature, public_key=args.public_key)
    except Exception as exc:
        console.print(f"[red]signature command failed: {exc}[/]")
        return 3
    console.print_json(data=result)
    return 0 if signature_ok(result) else 5


def _run_suggest_fix(name: str, console: Console) -> int:
    """Print the rewrites and the diff; exit 0 when nothing needs rewriting, 1 when a rewrite is suggested, 3 on a read error."""
    from monte_neo.verify.fixes import suggest_fixes

    try:
        result = suggest_fixes(Path(name).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        console.print(f"[red]{name}: cannot read: {exc}[/]", markup=True, highlight=False)
        return 3
    if result.get("error"):
        console.print(f"{name}: {result['error']}", markup=False, highlight=False)
        return 3
    if not result["changes"]:
        console.print(f"{name}: no rewrite suggested", markup=False, highlight=False)
        return 0
    for ch in result["changes"]:
        console.print(f"{name}:{ch['line']}: {ch['rule']}: {ch['before']}  ->  {ch['after']}  ({ch['note']})", markup=False, highlight=False)
    console.print(result["diff"], markup=False, highlight=False)
    console.print("The rewrite keeps the shape of the strategy, not its meaning: verify the patched file before using it.", markup=False)
    return 1


def _run_lint(paths: list[str], console: Console) -> int:
    """Lint strategy files; exit 1 when any file has a fail-severity finding, 3 when a file cannot be read."""
    from monte_neo.verify.lint import lint_source

    code = 0
    for name in paths:
        try:
            result = lint_source(Path(name).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            console.print(f"[red]{name}: cannot read: {exc}[/]", markup=True, highlight=False)
            return 3
        for f in result["findings"]:
            console.print(f"{name}:{f['line']}: {f['severity']} {f['rule']}: {f['message']}", markup=False, highlight=False)
        if result["status"] == "fail":
            code = 1
    return code


def precompile() -> float:
    """Run both engines once on tiny data so numba writes its cache; returns the seconds taken."""
    import time

    import numpy as np

    from monte_neo.backtest import synthetic_ohlcv
    from monte_neo.verify import verify_strategy

    start = time.perf_counter()
    df = synthetic_ohlcv(300, seed=0)
    signs = np.sign(np.sin(np.arange(len(df)) / 7.0))
    verify_strategy(df, signals=signs)  # sign engine
    verify_strategy(df, signals=0.5 * signs)  # target-weight engine
    return time.perf_counter() - start


def run(args: argparse.Namespace, console: Console | None = None) -> int:
    """Execute a parsed ``verify`` command."""
    from monte_neo.verify import (
        VERDICT_JSON_SCHEMA,
        load_ohlcv,
        model_from_costs,
        recheck_certificate,
        verify_grid,
        verify_strategy,
    )
    from monte_neo.verify.market import bar_count

    console = console or Console()
    if args.schema:
        console.print_json(data=VERDICT_JSON_SCHEMA)
        return 0
    if args.precompile:
        console.print(f"engines compiled and cached in {precompile():.1f} s")
        return 0
    if args.demo:
        return _run_demo(console)
    if args.demo_quotes:
        from monte_neo.cli.quotes_cmd import run_quotes_demo

        return run_quotes_demo(console)
    if args.quotes:
        from monte_neo.cli.quotes_cmd import run_quotes

        return run_quotes(args, console)
    if args.keygen or args.check_signature:
        return _run_signing(args, console)
    if args.lint:
        return _run_lint(args.lint, console)
    if args.suggest_fix:
        return _run_suggest_fix(args.suggest_fix, console)
    if args.render:
        from monte_neo.verify.recheck import load_certificate
        from monte_neo.verify.report_html import write_html

        if not args.html:
            console.print("[red]--render needs --html PATH[/]")
            return 3
        try:
            path = write_html(load_certificate(args.render), args.html)
        except Exception as exc:
            console.print(f"[red]render failed: {exc}[/]")
            return 3
        console.print(f"wrote {path}")
        return 0
    if not args.ohlcv or not (args.signals or args.strategy):
        console.print("[red]verify needs --ohlcv and one of --signals / --strategy[/]")
        return 3
    if args.recheck:
        try:
            result = recheck_certificate(
                args.recheck, args.ohlcv, signals=args.signals, strategy=args.strategy,
                jobs=args.jobs, timeout=args.timeout, isolate=args.isolate,
            )
        except Exception as exc:
            console.print(f"[red]recheck failed: {exc}[/]")
            return 3
        console.print_json(data=result)
        return 0 if result["reproduced"] else 4
    if args.grid and not args.strategy:
        console.print("[red]--grid needs --strategy (signal(df, **params))[/]")
        return 3
    try:
        df = load_ohlcv(args.ohlcv)
        model = model_from_costs(
            commission_bps=args.commission_bps,
            slippage_bps=args.slippage_bps,
            side_mode=_side_mode(args),
            warmup_bars=args.warmup_bars,
            n_bars=bar_count(df),
            funding_bps_per_bar=args.funding_bps_per_bar,
            borrow_bps_per_bar=args.borrow_bps_per_bar,
            sl_pct=args.sl_pct,
            tp_pct=args.tp_pct,
            trail_pct=args.trail_pct,
        )
        common = {
            "model": model, "periods_per_year": args.periods_per_year, "min_trades": args.min_trades,
            "positions": args.positions,
            "jobs": args.jobs,
            "timeout": args.timeout,
            "isolate": args.isolate,
            "claim": args.claim,
            "symbol_costs": args.costs_file,
        }
        if args.grid:
            report = verify_grid(df, _load_grid(args.grid), strategy=args.strategy, folds=args.folds, **common)
        else:
            report = verify_strategy(
                df, signals=args.signals, strategy=args.strategy, n_trials=args.n_trials,
                ledger=(True if args.ledger == "1" else args.ledger) or None,
                repaint=args.repaint, signal_timing=args.signal_timing, registration=args.registration, **common,
            )
    except Exception as exc:  # input errors must not look like a verdict
        console.print(f"[red]verify failed: {exc}[/]")
        return 3
    return _finish(report, args, console)


def _finish(report: dict[str, Any], args: argparse.Namespace, console: Console) -> int:
    """Sign, write the outputs, print, and return the verdict's exit code."""
    if args.sign:
        from monte_neo.verify.signing import sign_certificate

        try:
            report = sign_certificate(report, args.sign)
        except Exception as exc:
            console.print(f"[red]signing failed: {exc}[/]")
            return 3
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.html:
        from monte_neo.verify.report_html import write_html

        write_html(report, args.html)
    if args.badge:
        from monte_neo.verify.badge import badge_payload

        Path(args.badge).write_text(json.dumps(badge_payload(report), indent=2), encoding="utf-8")
    if args.format == "json":
        console.print_json(data=report)
    else:
        _render_text(report, console)
    return EXIT_CODES[report["verdict"]]


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``monte-neo verify`` and ``monte-neo-verify``."""
    try:
        args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        # argparse exits with 2 on a usage error, which the verifier reserves for REJECT: report it as 3.
        return 3 if exc.code == 2 else int(exc.code or 0)
    return run(args)


__all__ = ["EXIT_CODES", "build_parser", "main", "run"]
