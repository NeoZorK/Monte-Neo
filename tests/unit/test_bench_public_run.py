"""Unit tests for Honesty Bench public-run workspaces (prepare / collect / runner script)."""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
from pathlib import Path

import pytest
from rich.console import Console

from monte_neo.bench import init_bench, run_bench
from monte_neo.bench.public_run import ALIASES_FILE, DATA_HASHES_FILE, collect, prepare
from monte_neo.cli import bench_cmd

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "honesty_bench_run.sh"
STRATEGY = "import numpy as np\n\ndef signal(df):\n    return np.where(df['close'] > df['close'].rolling(20).mean(), 1, 0)\n"


@pytest.fixture()
def bench(tmp_path) -> Path:
    return init_bench(tmp_path / "hb", n_bars=400)


def _cli(argv: list[str]) -> tuple[int, str]:
    console = Console(record=True, width=200)
    return bench_cmd.main(argv, console), console.export_text()


def test_prepare_creates_clean_aliased_workspaces(bench, tmp_path) -> None:
    ws = tmp_path / "ws"
    info = prepare(bench, ws, ["alpha", "beta"], rng=random.Random(1))
    assert info["tasks"] == 5
    aliases = json.loads((bench / ALIASES_FILE).read_text())
    assert sorted(aliases) == [f"task-{n}" for n in range(1, 6)]
    assert sorted(aliases.values()) == sorted(p.name for p in (bench / "tasks").iterdir())
    for agent in ("alpha", "beta"):
        for alias in aliases:
            assert sorted(p.name for p in (ws / agent / alias).iterdir()) == ["PROMPT.md", "data.csv"]
    assert not list(ws.rglob("answer_key.json")) and not list(ws.rglob(ALIASES_FILE))
    assert len((bench / DATA_HASHES_FILE).read_text().splitlines()) == 5


def test_prepare_refuses_unsafe_setups(bench, tmp_path) -> None:
    with pytest.raises(ValueError, match="outside"):
        prepare(bench, bench / "ws", ["a"])
    with pytest.raises(ValueError, match="at least one"):
        prepare(bench, tmp_path / "ws0", [])
    with pytest.raises(ValueError, match="letters"):
        prepare(bench, tmp_path / "ws1", ["../evil"])
    (tmp_path / "busy").mkdir()
    (tmp_path / "busy" / "x").write_text("x")
    with pytest.raises(FileExistsError):
        prepare(bench, tmp_path / "busy", ["a"])
    with pytest.raises(FileNotFoundError, match="bench init"):
        prepare(tmp_path / "nothing", tmp_path / "ws2", ["a"])


def test_collect_maps_aliases_back_and_scores(bench, tmp_path) -> None:
    ws = tmp_path / "ws"
    prepare(bench, ws, ["alpha"], rng=random.Random(2))
    aliases = json.loads((bench / ALIASES_FILE).read_text())
    first, second = sorted(aliases)[:2]
    (ws / "alpha" / first / "strategy.py").write_text(STRATEGY)
    (ws / "alpha" / first / "claim.json").write_text('{"total_return": 0.3, "n_trials": 4}')
    (ws / "alpha" / first / "transcript.log").write_text("session")
    (ws / "alpha" / second / "strategy.py").write_text(STRATEGY)
    info = collect(bench, ws)
    assert sorted(info["collected"]) == sorted(f"alpha/{aliases[a]}" for a in (first, second))
    assert len(info["missing"]) == 3
    dest = bench / "submissions" / "alpha" / aliases[first]
    assert sorted(p.name for p in dest.iterdir()) == ["claim.json", "strategy.py", "transcript.log"]
    report = run_bench(bench)
    assert len(report["results"]) == 2
    with pytest.raises(FileNotFoundError, match="prepare"):
        collect(tmp_path / "nothing", ws)


def test_cli_prepare_and_collect(bench, tmp_path) -> None:
    code, text = _cli(["prepare", str(bench), "--agents", "a, b", "--workspaces", str(tmp_path / "ws")])
    assert code == 0 and "5 tasks x 2 agents" in text
    code, text = _cli(["prepare", str(bench), "--agents", "a", "--workspaces", str(tmp_path / "ws")])
    assert code == 3 and "prepare failed" in text
    code, text = _cli(["collect", str(bench), "--workspaces", str(tmp_path / "ws")])
    assert code == 0 and "collected 0" in text and "no strategy.py" in text
    code, text = _cli(["collect", str(tmp_path / "none"), "--workspaces", str(tmp_path / "ws")])
    assert code == 3 and "collect failed" in text


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_runner_script_runs_agent_command_per_task(bench, tmp_path) -> None:
    ws = tmp_path / "ws"
    prepare(bench, ws, ["fake-agent"], rng=random.Random(3))
    env = dict(os.environ)
    # The fake agent writes a strategy and echoes the first prompt line into the transcript.
    env["MN_CMD_fake_agent"] = f"printf '%s' {json.dumps(STRATEGY)} > strategy.py; echo \"$PROMPT\" | head -1"
    out = subprocess.run(["bash", str(SCRIPT), str(ws), "fake-agent"], env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    transcripts = sorted(ws.glob("fake-agent/task-*/transcript.log"))
    assert len(transcripts) == 5
    assert "You are given hourly OHLCV data" in transcripts[0].read_text()
    again = subprocess.run(["bash", str(SCRIPT), str(ws), "fake-agent"], env=env, capture_output=True, text=True, timeout=120)
    assert again.stdout.count("skip") == 5
    missing = subprocess.run(["bash", str(SCRIPT), str(ws), "unknown"], capture_output=True, text=True, timeout=60)
    assert missing.returncode == 2 and "MN_CMD_unknown" in missing.stderr
    assert collect(bench, ws)["missing"] == []
