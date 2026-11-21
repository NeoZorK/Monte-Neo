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
    p.add_argument("--funding", help="Funding history (.csv / .parquet: timestamp, symbol, funding_bps a long pays per bar): real funding on every perpetual leg")
    p.add_argument("--aum-grid", help="Comma-separated AUMs for the capacity grid in one run, for example 250000,500000,5000000")
    p.add_argument("--min-capacity", type=float, default=None, help="AUM at which the net return must stay positive (default: the largest of --aum-grid)")
    p.add_argument("--liquid-top", type=int, default=None, help="Trade only the K most liquid symbols by traded value known before each date (point-in-time universe; membership derived)")
    p.add_argument("--liquid-lookback", type=int, default=30, help="Bars of trailing traded value for --liquid-top (default 30)")
    p.add_argument("--terminal-returns", help="Delisted symbols (.csv: symbol, return): the return on the bar after the last price; undeclared delistings are flagged")
    p.add_argument("--rebalance-phase", help="K/H: rebalance on bar K of every H and hold the scores in between, to get the whole report for one phase")
    p.add_argument("--factors", help="Factor returns (.csv / .parquet: date + one column per factor) for attribution; default: built from the universe")
    p.add_argument("--book", help="Returns of your existing book (.csv / .parquet: date + one column per strategy): what does this signal add?")
    p.add_argument("--n-trials", type=int, default=1, help="Variants tried before this one (default 1)")
    p.add_argument(
        "--ledger", nargs="?", const="1", default=None, metavar="PATH",
        help="Count the score variants tried on these prices in an append-only ledger (default .monte-neo/ledger.jsonl); "
        "the larger of the count and --n-trials is used, and ARL levels 4 and above need this evidence",
    )
    p.add_argument("--membership", help="When each symbol was in the universe (.csv: symbol, start, end): catches today's members used for the past")
    p.add_argument("--groups", help="Sector or country per symbol (.csv: symbol, group[, as_of]): robustness by group")
    p.add_argument("--exchanges", help="Exchange per symbol (.csv: symbol, exchange such as XNYS, XLON, XTKS): closes of different markets")
    p.add_argument("--discovery-date", help="When the anomaly was published or found (YYYY-MM): how much of the edge is left after it")
    p.add_argument("--existing-scores", help="Scores of signals you already run (.csv: timestamp, symbol, one column per signal): is the new score new?")
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


DEMO_AUM = 2e5


def _write(path: str | None, payload: Any) -> None:
    if path:
        Path(path).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _terminal(path: str | None) -> dict[str, float] | None:
    if not path:
        return None
    import pandas as pd

    t = pd.read_csv(path)
    t.columns = [str(c).strip().lower() for c in t.columns]
    if "symbol" not in t.columns or "return" not in t.columns:
        raise ValueError("terminal returns need the columns symbol and return")
    return {str(s): float(r) for s, r in zip(t["symbol"], t["return"], strict=True)}


def main(argv: list[str]) -> int:
    """Run ``monte-neo alpha``; returns the process exit code."""
    from monte_neo.alpha import demo_panel, validate_alpha

    args = build_parser().parse_args(argv)
    console = Console(file=sys.stdout, soft_wrap=True)
    kw = {"horizon": args.horizon, "quantiles": args.quantiles, "claimed_ir": args.claim_ir, "seed": args.seed, "aum": args.aum,
          "factors": args.factors, "book": args.book, "n_trials": args.n_trials, "ledger": (True if args.ledger == "1" else args.ledger), "families": not args.signal_only,
          "membership": args.membership, "groups": args.groups, "exchanges": args.exchanges, "discovery_date": args.discovery_date,
          "existing": args.existing_scores, "funding": args.funding, "min_capacity": args.min_capacity,
          "aum_grid": [float(x) for x in args.aum_grid.split(",")] if args.aum_grid else None,
          "liquid_top": args.liquid_top, "liquid_lookback": args.liquid_lookback, "rebalance_phase": args.rebalance_phase,
          "terminal_returns": _terminal(args.terminal_returns)}
    try:
        if args.demo:
            prices, real, noise = demo_panel(2)
            if kw["aum"] is None:
                kw["aum"] = DEMO_AUM  # without a capital the tradability checks are skipped and both scores look alike
            reports = {"signal with a planted edge": validate_alpha(prices, real, **kw), "pure noise score": validate_alpha(prices, noise, **kw)}
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
            console.print(f"[dim]Demo capital: {DEMO_AUM:,.0f} (change it with --aum).[/]")
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
        console.print(f"    {rep['readiness']['headline']}: {rep['readiness']['summary']}")
    console.print(
        "  The planted score predicts returns and beats random scores; the noise score does not. "
        "It is idealised (40 independent names, a daily rebalance): real alpha is far weaker. "
        "With --aum, impact and participation show whether the predicting score is also tradable at that size."
    )
    console.print()
