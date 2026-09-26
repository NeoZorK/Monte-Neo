"""``monte-neo verify`` — CI-friendly strategy verifier command.

Exit codes: 0 PASS / PASS_WITH_WARNINGS, 1 NEEDS_MORE_EVIDENCE, 2 REJECT,
3 usage or input error, 4 certificate not reproduced (``--recheck``).
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
    src.add_argument("--signals", help="Positions per bar (.csv / .parquet / .npy): +1 long, 0 flat, -1 short")
    src.add_argument("--strategy", help="Strategy file 'path.py[:func]' with func(df) -> positions (default func: signal)")
    p.add_argument("--n-trials", type=int, default=None, help="How many variants were tried before this one")
    p.add_argument("--grid", help="Parameter grid as JSON or a .json file, e.g. '{\"fast\": [10, 20], \"slow\": [50, 100]}' (needs --strategy)")
    p.add_argument("--folds", type=int, default=4, help="Walk-forward folds for --grid (default 4)")
    p.add_argument("--commission-bps", type=float, default=5.0, help="Commission per side in bps (default 5)")
    p.add_argument("--slippage-bps", type=float, default=5.0, help="Slippage per side in bps (default 5)")
    p.add_argument("--side-mode", choices=["long_flat", "long_short"], default=None, help="Default: long_short if signals contain shorts")
    p.add_argument("--warmup-bars", type=int, default=None, help="Bars ignored before trading (default min(60, n/10))")
    p.add_argument("--periods-per-year", type=float, default=None, help="Bars per year for annualization (default: inferred)")
    p.add_argument("--min-trades", type=int, default=30, help="Minimum closed trades for statistics (default 30)")
    p.add_argument("--out", help="Write the strategy-verdict/1 JSON certificate to this path")
    p.add_argument("--recheck", help="Reproduce this certificate JSON from --ohlcv and --signals / --strategy")
    p.add_argument("--format", choices=["text", "json"], default="text", help="stdout format (default text)")
    p.add_argument("--schema", action="store_true", help="Print the strategy-verdict/1 JSON schema and exit")
    return p


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
    grid = report.get("grid")
    if grid:
        wf = grid["walk_forward"]
        console.print(
            f"grid: {grid['n_combos']} combos · best {grid['best_params']} · walk-forward OOS Sharpe/bar"
            f" {wf['oos_sharpe']:+.4f} · stability {wf['param_stability']:.2f}"
        )
    m = report.get("metrics") or {}
    if m:
        console.print(
            f"return {m['total_return']:+.2%} · maxDD {m['max_drawdown']:.2%} · trades {m['n_closed_trades']}"
            f" · Sharpe(ann) {m['sharpe_annualized']:.2f} · DSR {m['deflated_sharpe']:.3f}"
            f" · break-even {m['breakeven_cost_bps']:.1f} bps"
        )
    for action in report["next_actions"]:
        console.print(f"[yellow]→ {action}[/]")
    console.print(f"[dim]{report['disclaimer']}[/]")


def _load_grid(spec: str) -> dict[str, list[Any]]:
    text = Path(spec).read_text(encoding="utf-8") if spec.endswith(".json") and Path(spec).is_file() else spec
    grid = json.loads(text)
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

    console = console or Console()
    if args.schema:
        console.print_json(data=VERDICT_JSON_SCHEMA)
        return 0
    if not args.ohlcv or not (args.signals or args.strategy):
        console.print("[red]verify needs --ohlcv and one of --signals / --strategy[/]")
        return 3
    if args.recheck:
        try:
            result = recheck_certificate(args.recheck, args.ohlcv, signals=args.signals, strategy=args.strategy)
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
            n_bars=len(df),
        )
        common = {"model": model, "periods_per_year": args.periods_per_year, "min_trades": args.min_trades}
        if args.grid:
            report = verify_grid(df, _load_grid(args.grid), strategy=args.strategy, folds=args.folds, **common)
        else:
            report = verify_strategy(df, signals=args.signals, strategy=args.strategy, n_trials=args.n_trials, **common)
    except Exception as exc:  # input errors must not look like a verdict
        console.print(f"[red]verify failed: {exc}[/]")
        return 3
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.format == "json":
        console.print_json(data=report)
    else:
        _render_text(report, console)
    return EXIT_CODES[report["verdict"]]


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``monte-neo verify`` and ``monte-neo-verify``."""
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    return run(args)


__all__ = ["EXIT_CODES", "build_parser", "main", "run"]
