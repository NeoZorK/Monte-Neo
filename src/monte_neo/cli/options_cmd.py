"""``monte-neo verify --options FILE``: verify a table of option trades."""

from __future__ import annotations

import argparse

from rich.console import Console


def run_options(args: argparse.Namespace, console: Console) -> int:
    """Run the options checks; exit codes as ``verify`` (3 for an input error)."""
    from monte_neo.cli.verify_cmd import EXIT_CODES, _finish
    from monte_neo.options import verify_options

    try:
        report = verify_options(args.options, equity=args.equity, rate=args.rate, dividend_yield=args.dividend_yield, profile=True)
    except Exception as exc:  # input errors must not look like a verdict
        console.print(f"[red]options verify failed: {exc}[/]")
        return 3
    code = _finish(report, args, console)
    return code if code in EXIT_CODES.values() else 3
