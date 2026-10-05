"""``monte-neo bench run``: dry run, installed-CLI check, one run per task, first answer kept."""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from monte_neo.bench.agent_run import command_for, run_agents
from monte_neo.cli.bench_cmd import main


def _bench(tmp_path: Path, agent: str = "fake-agent") -> tuple[Path, Path]:
    bench, ws = tmp_path / "hb", tmp_path / "runs"
    assert main(["init", str(bench)], Console(quiet=True)) == 0
    assert main(["prepare", str(bench), "--agents", agent, "--workspaces", str(ws)], Console(quiet=True)) == 0
    return bench, ws


def test_defaults_and_the_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    assert command_for("claude-code").startswith("claude -p")
    monkeypatch.setenv("MN_CMD_gemini_cli", "echo hi")
    assert command_for("gemini-cli") == "echo hi"
    with pytest.raises(ValueError, match="MN_CMD_nobody"):
        command_for("nobody")


def test_a_dry_run_runs_nothing_and_a_missing_cli_stops_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, ws = _bench(tmp_path)
    monkeypatch.setenv("MN_CMD_fake_agent", "python3 -c pass")
    info = run_agents(ws, ["fake-agent"], dry_run=True)
    assert len(info["ran"]) == 5 and not list(ws.rglob("transcript.log"))
    monkeypatch.setenv("MN_CMD_fake_agent", "definitely-not-installed-cli --x")
    with pytest.raises(ValueError, match="not installed"):
        run_agents(ws, ["fake-agent"], dry_run=True)
    with pytest.raises(ValueError, match="no workspaces"):
        monkeypatch.setenv("MN_CMD_other", "python3 -c pass")
        run_agents(ws, ["other"])
    with pytest.raises(ValueError, match="does not exist"):
        run_agents(tmp_path / "nope", ["fake-agent"])


def test_each_task_runs_once_with_the_prompt_and_the_first_answer_is_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench, ws = _bench(tmp_path)
    agent = tmp_path / "agent.py"
    agent.write_text(
        "import json, os\nassert 'hourly OHLCV' in os.environ['PROMPT']\n"
        "open('strategy.py', 'w').write(\"def signal(df):\\n    return (df['close'] > df['close'].rolling(20).mean()).astype(int)\\n\")\n"
        "json.dump({'total_return': 0.1, 'sharpe': 1.0, 'n_trials': 2}, open('claim.json', 'w'))\n", encoding="utf-8")
    monkeypatch.setenv("MN_CMD_fake_agent", f"python3 {agent}")
    first = run_agents(ws, ["fake-agent"])
    assert len(first["ran"]) == 5 and all("exit 0" in r for r in first["ran"])
    log = (ws / "fake-agent" / "task-1" / "transcript.log").read_text()
    assert log.startswith("# agent: fake-agent") and "# exit: 0" in log
    again = run_agents(ws, ["fake-agent"])
    assert again["ran"] == [] and len(again["skipped"]) == 5
    assert main(["collect", str(bench), "--workspaces", str(ws)], Console(quiet=True)) == 0
    assert main([str(bench)], Console(quiet=True)) == 0


def test_the_cli_reports_errors_with_exit_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, ws = _bench(tmp_path)
    monkeypatch.setenv("MN_CMD_fake_agent", "definitely-not-installed-cli")
    assert main(["run", "--workspaces", str(ws), "--agents", "fake-agent", "--dry-run"], Console(quiet=True)) == 3
    monkeypatch.setenv("MN_CMD_fake_agent", "python3 -c pass")
    assert main(["run", "--workspaces", str(ws), "--agents", "fake-agent", "--dry-run"], Console(quiet=True)) == 0


def test_a_failing_agent_shows_its_output_and_exits_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, ws = _bench(tmp_path)
    bad = tmp_path / "bad.py"
    bad.write_text("import sys\nprint('Not logged in. Run login first.', file=sys.stderr)\nsys.exit(1)\n", encoding="utf-8")
    monkeypatch.setenv("MN_CMD_fake_agent", f"python3 {bad}")
    info = run_agents(ws, ["fake-agent"])
    assert len(info["failed"]) == 5 and "Not logged in" in info["failed"][0]
    assert main(["run", "--workspaces", str(ws), "--agents", "fake-agent"], Console(quiet=True)) == 4
