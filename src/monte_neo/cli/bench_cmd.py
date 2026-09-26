"""``monte-neo bench`` — run the Agent Backtest Honesty Bench over a directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console


def build_parser() -> argparse.ArgumentParser:
    """Argument parser for ``monte-neo bench``."""
    p = argparse.ArgumentParser(prog="monte-neo bench", description="Score agent-built strategies with the verifier.")
    p.add_argument("root", help="Bench directory with tasks/ and submissions/")
    p.add_argument("--out", help="Write the honesty-bench/1 JSON report here")
    p.add_argument("--markdown", help="Write the leaderboard as Markdown here")
    return p


def main(argv: list[str] | None = None, console: Console | None = None) -> int:
    """Entry point; exit 0 on success, 3 when the directory has no submissions."""
    from monte_neo.bench import render_markdown, run_bench

    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    console = console or Console()
    report = run_bench(args.root)
    if not report["results"]:
        console.print(f"[red]no submissions found under {args.root}/submissions/<agent>/<task>/strategy.py[/]")
        return 3
    table = render_markdown(report)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.markdown:
        Path(args.markdown).write_text(table, encoding="utf-8")
    console.print(table, soft_wrap=True)
    return 0


__all__ = ["build_parser", "main"]
