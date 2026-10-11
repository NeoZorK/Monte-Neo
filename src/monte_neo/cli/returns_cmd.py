"""``monte-neo verify --returns``: due diligence on a manager's return series (no code, no positions)."""

from __future__ import annotations

import argparse

from rich.console import Console

from monte_neo import disclaimer


def run_returns(args: argparse.Namespace, console: Console) -> int:
    """Verify a return series, or recheck a returns certificate (``--recheck``); returns the exit code."""
    from monte_neo.cli.verify_cmd import EXIT_CODES, _finish
    from monte_neo.verify.returns_dd import recheck_returns, verify_returns

    try:
        if args.recheck:
            from monte_neo.verify.recheck import load_certificate

            result = recheck_returns(load_certificate(args.recheck), args.returns, benchmark=args.benchmark)
            console.print_json(data=result)
            return 0 if result["reproduced"] else 4
        report = verify_returns(
            args.returns, benchmark=args.benchmark, n_strategies=args.n_strategies, claim=args.claim,
            periods_per_year=args.periods_per_year,
        )
    except Exception as exc:  # input errors must not look like a verdict
        console.print(f"[red]verify --returns failed: {exc}[/]")
        return 3
    code = _finish(report, args, console)
    return code if code in EXIT_CODES.values() else 3


def run_returns_demo(console: Console) -> int:
    """Three track records without files: honest, smoothed, and too good to be true."""
    from monte_neo.cli.verify_cmd import _VERDICT_STYLE
    from monte_neo.verify.returns_dd import demo_returns, verify_returns

    for name, series in demo_returns(0).items():
        report = verify_returns(series)
        flagged = [f"{c['id']} {c['status']}" for c in report["checks"] if c["status"] in ("fail", "warn")]
        console.print(f"[bold]{name.replace('_', ' ')}[/]: [{_VERDICT_STYLE[report['verdict']]}]{report['verdict']}[/]"
                      f"  ({', '.join(flagged) or 'no red flags'})")
    console.print("Your own: [bold]monte-neo verify --returns manager.csv [--benchmark index.csv] [--n-strategies N][/]")
    console.print(f"[dim]{disclaimer.SHORT}[/]")
    return 0


__all__ = ["run_returns", "run_returns_demo"]
