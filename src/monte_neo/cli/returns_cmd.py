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


def run_returns_batch(args: argparse.Namespace, console: Console) -> int:
    """Due diligence on every return file in ``--returns-dir``; exit 0 if no manager failed, 1 otherwise, 3 on input errors."""
    import json
    from pathlib import Path

    from rich.table import Table

    from monte_neo.cli.verify_cmd import _VERDICT_STYLE
    from monte_neo.verify.returns_batch import render_batch_html, verify_returns_batch

    try:
        result = verify_returns_batch(args.returns_dir, n_strategies=args.n_strategies, benchmark=args.benchmark)
        if not result["rows"]:
            raise ValueError(f"no readable return files in {args.returns_dir}: {len(result['errors'])} failed")
        if args.out:
            Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
        if args.html:
            Path(args.html).write_text(render_batch_html(result), encoding="utf-8")
    except Exception as exc:
        console.print(f"[red]verify --returns-dir failed: {exc}[/]")
        return 3
    table = Table(title="Manager due diligence")
    for col in ("Manager", "Verdict", "Sharpe", "Unsmoothed", "Max DD", "Red flags"):
        table.add_column(col)
    for r in result["rows"]:
        table.add_row(r["manager"], f"[{_VERDICT_STYLE[r['verdict']]}]{r['verdict']}[/]", f"{r['sharpe']:.2f}",
                      f"{r['unsmoothed_sharpe']:.2f}", f"{r['max_drawdown'] * 100:.1f}%", ", ".join(r["red_flags"]) or "none")
    console.print(table)
    for e in result["errors"]:
        console.print(f"[yellow]skipped {e['file']}: {e['error']}[/]")
    console.print(f"[dim]{disclaimer.SHORT}[/]")
    return 1 if any(r["verdict"] in ("REJECT", "NEEDS_MORE_EVIDENCE") for r in result["rows"]) else 0


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


__all__ = ["run_returns", "run_returns_batch", "run_returns_demo"]
