"""``monte-neo bench detect``: the known-error table from the command line."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from monte_neo.cli.bench_cmd import main


def _run(argv: list[str]) -> tuple[int, str]:
    console = Console(record=True, width=160)
    code = main(argv, console)
    return code, console.export_text()


def test_detect_one_case_writes_reports(tmp_path: Path) -> None:
    out, md = tmp_path / "r.json", tmp_path / "r.md"
    code, text = _run(["detect", "--seeds", "1", "--case", "next_bar_leak", "--case", "noise_strategy", "--out", str(out), "--markdown", str(md)])
    report = json.loads(out.read_text())
    assert set(report["cases"]) == {"next_bar_leak", "noise_strategy"} and report["seeds"] == 1
    assert "next_bar_leak" in text and "| Case |" in md.read_text()
    assert code == 0


def test_detect_rejects_bad_arguments() -> None:
    assert _run(["detect", "--seeds", "0"])[0] == 3
    code, text = _run(["detect", "--case", "no_such_case"])
    assert code == 3 and "unknown case" in text


def test_bench_help_lists_subcommands() -> None:
    """The top-level bench help names the subcommands that the guides use."""
    from monte_neo.cli.bench_cmd import build_parser

    text = build_parser().format_help()
    for name in ("init", "prepare", "run", "collect", "detect"):
        assert name in text
