"""``monte-neo bench`` — run the Agent Backtest Honesty Bench over a directory.

``monte-neo bench init <dir>`` writes the deterministic Honesty Bench v1 tasks.
``monte-neo bench prepare <dir> --agents a,b --workspaces <out>`` creates one clean
workspace per agent and task; ``monte-neo bench collect <dir> --workspaces <out>``
copies the agents' files back into ``submissions/``.
"""

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


def _init(argv: list[str], console: Console) -> int:
    from monte_neo.bench.tasks_v1 import BENCH_VERSION, init_bench

    p = argparse.ArgumentParser(prog="monte-neo bench init", description="Write the Honesty Bench v1 tasks.")
    p.add_argument("dest", help="Directory to create")
    p.add_argument("--bars", type=int, default=5000, help="Bars per task (default 5000)")
    args = p.parse_args(argv)
    root = init_bench(args.dest, n_bars=args.bars)
    console.print(f"{BENCH_VERSION} written to {root}")
    console.print("Give each agent tasks/<id>/data.csv + PROMPT.md; save its files to submissions/<agent>/<id>/.")
    console.print("Keep answer_key.json away from the agents.")
    return 0


def _prepare(argv: list[str], console: Console) -> int:
    from monte_neo.bench.public_run import prepare

    p = argparse.ArgumentParser(prog="monte-neo bench prepare", description="Create clean workspaces for a public run.")
    p.add_argument("root", help="Bench directory written by `monte-neo bench init`")
    p.add_argument("--agents", required=True, help="Comma-separated agent names, e.g. claude-code,codex,gemini-cli,cursor")
    p.add_argument("--workspaces", required=True, help="Directory to create, outside the bench directory")
    args = p.parse_args(argv)
    try:
        info = prepare(args.root, args.workspaces, [a.strip() for a in args.agents.split(",") if a.strip()])
    except (ValueError, FileExistsError, FileNotFoundError) as exc:
        console.print(f"[red]prepare failed: {exc}[/]")
        return 3
    console.print(f"{info['tasks']} tasks x {len(info['agents'])} agents in {info['workspaces']}")
    console.print("Each workspace holds only data.csv and PROMPT.md. Task names are replaced by task-1..N;")
    console.print(f"the map is in {info['aliases_file']}. Keep it and answer_key.json away from the agents.")
    return 0


def _collect(argv: list[str], console: Console) -> int:
    from monte_neo.bench.public_run import collect

    p = argparse.ArgumentParser(prog="monte-neo bench collect", description="Copy agent outputs into submissions/.")
    p.add_argument("root", help="Bench directory")
    p.add_argument("--workspaces", required=True, help="Directory created by `monte-neo bench prepare`")
    args = p.parse_args(argv)
    try:
        info = collect(args.root, args.workspaces)
    except FileNotFoundError as exc:
        console.print(f"[red]collect failed: {exc}[/]")
        return 3
    console.print(f"collected {len(info['collected'])} submissions")
    for item in info["missing"]:
        console.print(f"[yellow]no strategy.py: {item}[/]")
    return 0


def main(argv: list[str] | None = None, console: Console | None = None) -> int:
    """Entry point; exit 0 on success, 3 when the directory has no submissions."""
    from monte_neo.bench import render_markdown, run_bench

    argv = sys.argv[1:] if argv is None else argv
    console = console or Console()
    if argv and argv[0] == "init":
        return _init(argv[1:], console)
    if argv and argv[0] == "prepare":
        return _prepare(argv[1:], console)
    if argv and argv[0] == "collect":
        return _collect(argv[1:], console)
    args = build_parser().parse_args(argv)
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
