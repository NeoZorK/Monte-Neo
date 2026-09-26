"""Unit tests for the Agent Backtest Honesty Bench."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from rich.console import Console

from monte_neo.bench import load_bench, render_markdown, run_bench, score_submission, summarize_agents
from monte_neo.cli import app, bench_cmd

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bench_dir(tmp_path_factory) -> Path:
    spec = importlib.util.spec_from_file_location("make_example_bench", ROOT / "scripts" / "make_example_bench.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    root = mod.build(tmp_path_factory.mktemp("bench") / "b")
    # an agent with a broken submission and one for an unknown task
    broken = root / "submissions" / "broken-agent" / "trend"
    broken.mkdir(parents=True)
    (broken / "strategy.py").write_text("def signal(df):\n    raise ValueError('boom')\n")
    ghost = root / "submissions" / "broken-agent" / "no-such-task"
    ghost.mkdir(parents=True)
    (ghost / "strategy.py").write_text("def signal(df):\n    return df.close * 0\n")
    return root


def test_load_bench(bench_dir) -> None:
    bench = load_bench(bench_dir)
    assert set(bench["tasks"]) == {"trend", "mean-reversion"}
    assert len(bench["submissions"]) == 6
    assert bench["tasks"]["trend"]["ohlcv_path"].endswith("data.csv")


def test_run_bench_ranks_careful_agent_first(bench_dir) -> None:
    report = run_bench(bench_dir)
    json.dumps(report, allow_nan=False)
    board = {r["agent"]: r for r in report["leaderboard"]}
    assert report["leaderboard"][0]["agent"] == "careful-agent"
    assert board["careful-agent"]["lookahead_rate"] == 0.0 and board["careful-agent"]["overclaim_rate"] == 0.0
    assert board["eager-agent"]["lookahead_rate"] == 1.0 and board["eager-agent"]["overclaim_rate"] == 1.0
    assert board["eager-agent"]["declared_n_trials_rate"] == 0.0
    assert board["broken-agent"]["error_rate"] == 1.0 and board["broken-agent"]["median_return_gap"] is None
    md = render_markdown(report)
    assert md.startswith("# Agent Backtest Honesty Bench") and "| 1 | careful-agent |" in md


def test_score_without_claim(bench_dir) -> None:
    bench = load_bench(bench_dir)
    first = next(s for s in bench["submissions"] if s["agent"] == "careful-agent")
    sub = {**first, "claim": {}}
    row = score_submission(bench["tasks"][sub["task"]], sub)
    assert row["overclaim"] is None and row["return_gap"] is None and row["n_trials_declared"] is False


def test_summarize_empty() -> None:
    assert summarize_agents([]) == []


def test_bench_cli(bench_dir, tmp_path, monkeypatch) -> None:
    out, md = tmp_path / "r.json", tmp_path / "board.md"
    console = Console(record=True, width=200)
    assert bench_cmd.main([str(bench_dir), "--out", str(out), "--markdown", str(md)], console) == 0
    assert json.loads(out.read_text())["schema"] == "honesty-bench/1"
    assert "careful-agent" in md.read_text() and "careful-agent" in console.export_text()
    empty = tmp_path / "empty"
    empty.mkdir()
    assert bench_cmd.main([str(empty)], Console(record=True)) == 3
    monkeypatch.setattr(bench_cmd, "main", lambda argv=None: 5)
    monkeypatch.setattr(sys, "argv", ["monte-neo", "bench", str(bench_dir)])
    assert app.main() == 5
    monkeypatch.setattr(sys, "argv", ["monte-neo-bench", str(empty)])
