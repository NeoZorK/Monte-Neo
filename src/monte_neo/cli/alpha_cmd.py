"""``monte-neo alpha`` — does a cross-sectional signal have real predictive power?

Exit codes: 0 PASS / PASS_WITH_WARNINGS, 1 NEEDS_MORE_EVIDENCE, 2 REJECT, 3 usage or input error.
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
    """Argument parser for ``monte-neo alpha``."""
    p = argparse.ArgumentParser(prog="monte-neo alpha", description="Check whether a cross-sectional signal has real predictive power.")
    p.add_argument("--ohlcv", help="Prices universe (.csv / .parquet): timestamp, symbol, close[, volume]")
    p.add_argument("--scores", help="Scores table (.csv / .parquet): timestamp (or date), symbol, score")
    p.add_argument("--horizon", type=int, default=1, help="Forward-return horizon in bars (default 1)")
    p.add_argument("--quantiles", type=int, default=5, help="Quantile buckets (default 5)")
    p.add_argument("--claim-ir", type=float, default=None, help="Claimed annual information ratio (enables the breadth check)")
    p.add_argument("--aum", type=float, default=None, help="Capital you plan to run (quote currency): enables the market-impact and participation checks")
    p.add_argument("--factors", help="Factor returns (.csv / .parquet: date + one column per factor) for attribution; default: built from the universe")
    p.add_argument("--book", help="Returns of your existing book (.csv / .parquet: date + one column per strategy): what does this signal add?")
    p.add_argument("--n-trials", type=int, default=1, help="Variants tried before this one (default 1)")
    p.add_argument("--signal-only", action="store_true", help="Only signal power and implementability (skip attribution, book, multiple testing, risk)")
    p.add_argument("--seed", type=int, default=0, help="Seed for bootstraps and placebos (default 0)")
    p.add_argument("--format", choices=["text", "json"], default="text", help="stdout format (default text)")
    p.add_argument("--out", help="Write the alpha-report/1 JSON to this path")
    p.add_argument("--demo", action="store_true", help="Try it with no files: a weakly predictive score and a noise score on synthetic data")
    return p


def _render(report: dict[str, Any], console: Console, title: str | None = None) -> None:
    if title:
        console.print(f"[bold]{title}[/]")
    console.print(f"[{_VERDICT_STYLE[report['verdict']]}]{report['verdict']}[/]")
    table = Table(show_header=True, header_style="bold")
    for col in ("check", "category", "status", "summary"):
        table.add_column(col)
    for c in report["checks"]:
        table.add_row(c["id"], c["category"], f"[{_STATUS_STYLE.get(c['status'], '')}]{c['status']}[/]", c["summary"])
    console.print(table)
    if report["next_actions"]:
        console.print(f"[bold]Next:[/] {report['next_actions'][0]}")


def _write(path: str | None, payload: Any) -> None:
    if path:
        Path(path).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    """Run ``monte-neo alpha``; returns the process exit code."""
    from monte_neo.alpha import demo_panel, validate_alpha

    args = build_parser().parse_args(argv)
    console = Console(file=sys.stdout, soft_wrap=True)
    kw = {"horizon": args.horizon, "quantiles": args.quantiles, "claimed_ir": args.claim_ir, "seed": args.seed, "aum": args.aum,
          "factors": args.factors, "book": args.book, "n_trials": args.n_trials, "families": not args.signal_only}
    try:
        if args.demo:
            prices, real, noise = demo_panel(2)
            reports = {"signal with a real weak edge": validate_alpha(prices, real, **kw), "pure noise score": validate_alpha(prices, noise, **kw)}
        elif args.ohlcv and args.scores:
            reports = {"": validate_alpha(args.ohlcv, args.scores, **kw)}
        else:
            console.print("[red]error:[/] give --ohlcv and --scores, or --demo")
            return 3
    except (ValueError, OSError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    if args.format == "json":
        payload: Any = next(iter(reports.values())) if len(reports) == 1 else reports
        print(json.dumps(payload, indent=2, allow_nan=False))
    else:
        for name, rep in reports.items():
            _render(rep, console, name or None)
            console.print()
    _write(args.out, next(iter(reports.values())) if len(reports) == 1 else reports)
    code = max(EXIT_CODES[r["verdict"]] for r in reports.values())
    if args.format == "text":
        if args.demo:
            _demo_summary(reports, console)
        console.print(f"[dim]{next(iter(reports.values()))['disclaimer']}[/]")
    return code


def _demo_summary(reports: dict[str, dict[str, Any]], console: Console) -> None:
    """One line per demo score: its verdict and the checks that decided it."""
    console.print("[bold]In short:[/]")
    for name, rep in reports.items():
        failed = [c["id"] for c in rep["checks"] if c["status"] == "fail"]
        warned = [c["id"] for c in rep["checks"] if c["status"] == "warn"]
        why = f"failed {', '.join(failed)}" if failed else (f"warnings {', '.join(warned)}" if warned else "every check passed")
        console.print(f"  {name}: [{_VERDICT_STYLE.get(rep['verdict'], 'bold')}]{rep['verdict']}[/] ({why})")
    console.print(
        "  The real score predicts returns and beats random scores; the noise score does not. "
        "With --aum, impact and participation show whether the predicting score is also tradable at that size."
    )
    console.print()
