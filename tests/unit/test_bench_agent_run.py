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
    assert len(info["failed"]) == 1 and len(info["ran"]) == 1 and "Not logged in" in info["failed"][0]  # the other tasks are not run
    assert main(["run", "--workspaces", str(ws), "--agents", "fake-agent"], Console(quiet=True)) == 4


def test_a_pinned_model_is_appended_for_known_agents_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, ws = _bench(tmp_path, "claude-code")
    monkeypatch.setenv("MN_CMD_claude_code", "python3 -c pass")
    info = run_agents(ws, ["claude-code"], dry_run=True, model="sonnet")
    assert info["ran"][0].endswith("python3 -c pass --model sonnet")
    monkeypatch.setenv("MN_CMD_odd", "python3 -c pass")
    with pytest.raises(ValueError, match="--model is not known"):
        run_agents(ws, ["odd"], dry_run=True, model="x")


def _serve(status: int = 200) -> tuple[object, str]:
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(status)
            self.end_headers()

        def log_message(self, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/v1"


def test_qwen_code_is_a_known_agent_with_a_model_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert command_for("qwen-code") == 'qwen "$PROMPT" --yolo'
    _, ws = _bench(tmp_path, "qwen-code")
    monkeypatch.setenv("MN_CMD_qwen_code", "python3 -c pass")
    info = run_agents(ws, ["qwen-code"], dry_run=True, model="qwen3-coder")
    assert info["ran"][0].endswith("python3 -c pass --model qwen3-coder")


def test_a_local_server_url_reaches_the_agent_as_the_openai_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, ws = _bench(tmp_path, "qwen-code")
    server, url = _serve()
    agent = tmp_path / "env_agent.py"
    agent.write_text(
        "import os\nassert os.environ['OPENAI_BASE_URL'].endswith('/v1')\nassert os.environ['OPENAI_API_KEY'] == 'local'\n"
        "assert os.environ['OPENAI_MODEL'] == 'qwen3-coder'\nopen('strategy.py', 'w').write('def signal(df):\\n    return df[\"close\"] * 0\\n')\n",
        encoding="utf-8")
    monkeypatch.setenv("MN_CMD_qwen_code", f"python3 {agent}")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    try:
        info = run_agents(ws, ["qwen-code"], model="qwen3-coder", base_url=url)
    finally:
        server.shutdown()  # type: ignore[attr-defined]
    assert len(info["ran"]) == 5 and not info["failed"]


def test_an_unreachable_or_odd_local_url_stops_before_any_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, ws = _bench(tmp_path, "qwen-code")
    monkeypatch.setenv("MN_CMD_qwen_code", "python3 -c pass")
    with pytest.raises(ValueError, match="not reachable"):
        run_agents(ws, ["qwen-code"], dry_run=True, base_url="http://127.0.0.1:9/v1")
    with pytest.raises(ValueError, match="http"):
        run_agents(ws, ["qwen-code"], dry_run=True, base_url="localhost:11434")
    assert not list(ws.rglob("transcript.log"))
    server, url = _serve(404)  # an HTTP answer of any kind means the server is up
    try:
        assert run_agents(ws, ["qwen-code"], dry_run=True, base_url=url)["dry_run"]
    finally:
        server.shutdown()  # type: ignore[attr-defined]


def test_known_failure_texts_get_a_one_line_fix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from monte_neo.bench.agent_run import hint_for

    assert "OPENAI_BASE_URL" in hint_for("No auth type is selected. Please configure")
    assert "ollama serve" in hint_for("Error: connect ECONNREFUSED 127.0.0.1:11434")
    assert hint_for("something else") == ""
    _, ws = _bench(tmp_path)
    bad = tmp_path / "noauth.py"
    bad.write_text("import sys\nprint('No auth type is selected.', file=sys.stderr)\nsys.exit(1)\n", encoding="utf-8")
    monkeypatch.setenv("MN_CMD_fake_agent", f"python3 {bad}")
    info = run_agents(ws, ["fake-agent"])
    assert "-> no model is configured" in info["failed"][0]
    assert main(["run", "--workspaces", str(ws), "--agents", "fake-agent", "--base-url", "ftp://x"], Console(quiet=True)) == 3
