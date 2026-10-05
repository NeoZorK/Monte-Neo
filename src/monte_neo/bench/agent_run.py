"""Run coding agents headless over Honesty Bench workspaces (``monte-neo bench run``).

Each agent runs once per task, in a new session, with the task folder as its working directory and ``PROMPT.md``
as its only instruction (an argument ``$PROMPT`` of the command is replaced by it; it is also in the environment as ``PROMPT``). The full output goes to ``transcript.log``.
A task that already has a ``strategy.py`` is never run again: the first final answer is the one that counts.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_COMMANDS = {
    "claude-code": 'claude -p "$PROMPT" --permission-mode acceptEdits',
    "codex": 'codex exec --full-auto "$PROMPT"',
    "gemini-cli": 'gemini -p "$PROMPT" --yolo',
    "cursor": 'cursor-agent -p "$PROMPT" --force',
}


def command_for(agent: str) -> str:
    """The shell command of ``agent``: ``MN_CMD_<agent>`` (dashes become underscores) or the default."""
    cmd = os.environ.get("MN_CMD_" + agent.replace("-", "_")) or DEFAULT_COMMANDS.get(agent, "")
    if not cmd:
        raise ValueError(f"no command for agent {agent!r}: set MN_CMD_{agent.replace('-', '_')}")
    return cmd


MODEL_FLAGS = {"claude-code": "--model", "codex": "--model", "gemini-cli": "--model"}


def run_agents(
    workspaces: str | Path, agents: list[str], *, dry_run: bool = False, timeout: int = 3600, model: str | None = None
) -> dict[str, Any]:
    """Run (or, with ``dry_run``, list) every task of every agent. Raises ``ValueError`` before running anything on a bad setup."""
    root = Path(workspaces)
    if not root.is_dir():
        raise ValueError(f"{root} does not exist: run `monte-neo bench prepare` first")
    plan: list[tuple[str, Path, str]] = []
    for agent in agents:
        cmd = command_for(agent)
        if model:
            if agent not in MODEL_FLAGS:
                raise ValueError(f"--model is not known for agent {agent!r}: put the model into MN_CMD_{agent.replace('-', '_')}")
            cmd = f"{cmd} {MODEL_FLAGS[agent]} {shlex.quote(model)}"
        first = shlex.split(cmd)[0]
        if shutil.which(first) is None:
            raise ValueError(f"agent {agent!r}: {first!r} is not installed or not on PATH (set MN_CMD_{agent.replace('-', '_')} to the right command)")
        tasks = sorted(p for p in (root / agent).glob("task-*") if p.is_dir())
        if not tasks:
            raise ValueError(f"no workspaces for agent {agent!r} under {root}: was it listed in `monte-neo bench prepare --agents`?")
        plan += [(agent, t, cmd) for t in tasks]
    done, skipped, failed = [], [], []
    for agent, task, cmd in plan:
        if (task / "strategy.py").exists():
            skipped.append(str(task))
            continue
        if dry_run:
            done.append(f"{agent} {task.name}: {cmd}")
            continue
        env = {**os.environ, "PROMPT": (task / "PROMPT.md").read_text(encoding="utf-8")}
        header = f"# agent: {agent}\n# started: {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}\n# command: {cmd}\n\n"
        try:
            argv = [env["PROMPT"] if tok in ("$PROMPT", "${PROMPT}") else tok for tok in shlex.split(cmd)]  # no shell: the prompt is one argument
            proc = subprocess.run(argv, cwd=task, env=env, capture_output=True, text=True, timeout=timeout, check=False)  # noqa: S603 - the user's own agent command
            body, code = proc.stdout + proc.stderr, str(proc.returncode)
        except subprocess.TimeoutExpired as exc:
            body, code = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""), f"timeout after {timeout}s"
        (task / "transcript.log").write_text(f"{header}{body}\n# exit: {code}\n# finished: {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}\n", encoding="utf-8")
        done.append(f"{agent} {task.name}: exit {code}")
        if code != "0":
            failed.append(f"{agent} {task.name} (exit {code}): {body.strip()[-400:] or 'no output'}")
    return {"ran": done, "skipped": skipped, "failed": failed, "dry_run": dry_run}
