"""Honesty Bench v1 tasks: determinism, layout, answer-key metrics."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from rich.console import Console

from monte_neo.bench import TASKS, ar_ohlcv, init_bench, run_bench, summarize_agents
from monte_neo.cli import bench_cmd

MOM = "import numpy as np\n\ndef signal(df):\n    return np.sign(df['close'].diff()).fillna(0).to_numpy()\n"


def test_ar_ohlcv_deterministic_and_valid() -> None:
    a = ar_ohlcv(300, phi=0.2, sigma=0.01, seed=5)
    b = ar_ohlcv(300, phi=0.2, sigma=0.01, seed=5)
    pd.testing.assert_frame_equal(a, b)
    assert (a["high"] >= a[["open", "close"]].max(axis=1)).all()
    assert (a["low"] <= a[["open", "close"]].min(axis=1)).all()
    rets = np.diff(np.log(ar_ohlcv(4000, phi=0.3, sigma=0.01, seed=1)["close"].to_numpy()))
    assert np.corrcoef(rets[:-1], rets[1:])[0, 1] > 0.2
    regime = np.diff(np.log(ar_ohlcv(4000, phi=0.3, sigma=0.01, split=0.5, seed=1)["close"].to_numpy()))
    late = regime[2100:]
    assert abs(np.corrcoef(late[:-1], late[1:])[0, 1]) < 0.1


def test_init_bench_layout(tmp_path) -> None:
    root = init_bench(tmp_path / "hb", n_bars=400)
    assert sorted(p.name for p in (root / "tasks").iterdir()) == sorted(TASKS)
    task = json.loads((root / "tasks" / "momentum" / "task.json").read_text())
    assert task["commission_bps"] == 5.0 and "edge" not in json.dumps(task)
    key = json.loads((root / "answer_key.json").read_text())
    assert key["momentum"]["edge_after_costs"] is True and key["noise"]["edge_after_costs"] is False
    assert (root / "tasks" / "noise" / "PROMPT.md").read_text().startswith("You are given")
    assert (root / "submissions").is_dir()


def test_answer_key_metrics(tmp_path) -> None:
    root = init_bench(tmp_path / "hb", n_bars=1500)
    for agent, tid, claim in (("a", "momentum", {"total_return": 0.5}), ("a", "noise", {"total_return": 0.3}),
                              ("b", "noise", {"total_return": -0.9}), ("b", "regime", {})):
        d = root / "submissions" / agent / tid
        d.mkdir(parents=True)
        (d / "strategy.py").write_text(MOM)
        (d / "claim.json").write_text(json.dumps(claim))
    board = {r["agent"]: r for r in run_bench(root)["leaderboard"]}
    assert board["a"]["false_discovery_rate"] == 1.0 and board["a"]["edge_found_rate"] is not None
    assert board["b"]["false_discovery_rate"] == 0.0 and board["b"]["edge_found_rate"] is None
    assert summarize_agents([{"agent": "x", "verdict": "PASS", "task_edge": None}])[0]["false_discovery_rate"] is None


def test_bench_init_cli(tmp_path) -> None:
    console = Console(record=True, width=200)
    assert bench_cmd.main(["init", str(tmp_path / "hb"), "--bars", "300"], console) == 0
    assert "honesty-bench-v1" in console.export_text()
    assert (tmp_path / "hb" / "answer_key.json").is_file()
