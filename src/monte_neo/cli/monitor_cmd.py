"""``monte-neo monitor`` — is the live (or paper) strategy behaving like its backtest, and is the alpha dead?

Exit codes: 0 no warning, 2 at least one warning (for cron and CI), 3 input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from monte_neo import disclaimer

_STYLE = {"pass": "green", "info": "cyan", "warn": "yellow", "skip": "dim"}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="monte-neo monitor", description="Compare live results with the backtest and watch for a dead edge.")
    p.add_argument("--certificate", help="strategy-verdict/1 certificate (JSON) holding the backtest")
    p.add_argument("--backtest", help="backtest returns file (date, return)")
    p.add_argument("--live", help="live returns file (date, return), or a fills file")
    p.add_argument("--fills", help="fills file: timestamp, symbol, side, quantity, price, [fee], [reference_price]")
    p.add_argument("--slippage-bps", type=float, default=None, help="modelled slippage in bps (default: from the certificate)")
    p.add_argument("--haircut", type=float, default=0.5, help="share of the backtest mean expected live (default 0.5)")
    p.add_argument("--format", choices=("text", "json"), default="text")
    p.add_argument("--out", help="also write the JSON report to this path")
    return p


def main(argv: list[str] | None = None) -> int:
    """Run ``monte-neo monitor``; returns the exit code."""
    console = Console()
    try:
        args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return 3 if exc.code == 2 else int(exc.code or 0)
    try:
        if bool(args.certificate) == bool(args.backtest):
            raise ValueError("give exactly one of --certificate or --backtest")
        if not args.live and not args.fills:
            raise ValueError("give --live (returns or fills) and/or --fills")
        if not 0.0 < args.haircut <= 1.0:
            raise ValueError("--haircut must be in (0, 1]")
        from monte_neo.verify.live import load_live, verify_live
        from monte_neo.verify.recheck import load_certificate

        source = load_certificate(args.certificate) if args.certificate else args.backtest
        live = load_live(args.live) if args.live else {"kind": "fills", "returns": None, "fills": None}
        report = verify_live(source, live, fills=args.fills, modelled_slippage_bps=args.slippage_bps, haircut=args.haircut)
        if args.out:
            Path(args.out).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    except Exception as exc:  # input errors must not look like a warning
        console.print(f"[red]monitor failed: {exc}[/]")
        return 3
    if args.format == "json":
        print(json.dumps(report, indent=2, default=str))
    else:
        table = Table(title=f"Live monitor: {report['status'].upper()}")
        for col in ("check", "status", "summary"):
            table.add_column(col, overflow="fold")
        for c in report["checks"]:
            table.add_row(c["id"], f"[{_STYLE.get(c['status'], 'white')}]{c['status']}[/]", c["summary"])
        console.print(table)
        for action in report["next_actions"]:
            console.print(f"- {action}")
    if args.format == "json":
        print(disclaimer.SHORT)
    else:
        console.print(f"[dim]{disclaimer.SHORT}[/]")
    return 2 if report["status"] == "warn" else 0


__all__ = ["main"]
