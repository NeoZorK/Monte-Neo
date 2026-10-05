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
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_COMMANDS = {
    # Bash is allowed: the agent has to run its own backtests, and a headless session cannot ask for approval.
    "claude-code": 'claude -p "$PROMPT" --permission-mode acceptEdits --allowedTools "Bash Read Write Edit"',
    "codex": 'codex exec --full-auto "$PROMPT"',
    "gemini-cli": 'gemini -p "$PROMPT" --yolo',
    "cursor": 'cursor-agent -p "$PROMPT" --force',
    # Qwen Code reads OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL, so it also drives a local model (Ollama, LM Studio, llama.cpp).
    "qwen-code": 'qwen "$PROMPT" --yolo',
}


def command_for(agent: str) -> str:
    """The shell command of ``agent``: ``MN_CMD_<agent>`` (dashes become underscores) or the default."""
    cmd = os.environ.get("MN_CMD_" + agent.replace("-", "_")) or DEFAULT_COMMANDS.get(agent, "")
    if not cmd:
        raise ValueError(f"no command for agent {agent!r}: set MN_CMD_{agent.replace('-', '_')}")
    return cmd


# The agent's own warning about running without a sandbox is not output we want in every transcript.
AGENT_ENV = {"qwen-code": {"QWEN_CODE_SUPPRESS_YOLO_WARNING": "1"}}
MODEL_FLAGS = {"claude-code": "--model", "codex": "--model", "gemini-cli": "--model", "qwen-code": "--model"}

# Known failure texts and what to do about them (shown under the agent's own output).
HINTS = (
    ("No auth type is selected", "no model is configured: pass --base-url (a local server) or set OPENAI_BASE_URL, OPENAI_API_KEY and OPENAI_MODEL"),
    ("Connection error", "the agent could not reach its model server: is it running and is the address right (Ollama: `ollama serve`, http://localhost:11434/v1)?"),
    ("ECONNREFUSED", "the model server refused the connection: is it running (for Ollama: `ollama serve`)?"),
    ("Connection refused", "the model server refused the connection: is it running (for Ollama: `ollama serve`)?"),
    ("model not found", "the server has no such model: list the models with `ollama list` and pull one with `ollama pull <name>`"),
    ("not found, try pulling it", "the server has no such model: pull it with `ollama pull <name>`"),
)


def hint_for(output: str) -> str:
    """A one-line fix for a known failure text, or an empty string."""
    low = output.lower()
    return next((h for key, h in HINTS if key.lower() in low), "")


def check_endpoint(base_url: str, timeout: float = 5.0) -> None:
    """Fail before any task runs when the OpenAI-compatible server cannot be reached (any HTTP answer counts as reachable)."""
    if not base_url.startswith(("http://", "https://")):
        raise ValueError(f"--base-url must start with http:// or https://, got {base_url!r}")
    url = base_url.rstrip("/") + "/models"
    try:
        urllib.request.urlopen(url, timeout=timeout).close()  # noqa: S310  # nosec B310 - scheme checked above
    except urllib.error.HTTPError:
        return  # the server answered (401, 404, ...): it is up
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise ValueError(f"the model server at {base_url} is not reachable ({exc}); start it first (Ollama: `ollama serve`)") from exc


def run_agents(
    workspaces: str | Path, agents: list[str], *, dry_run: bool = False, timeout: int = 3600, model: str | None = None,
    base_url: str | None = None, api_key: str | None = None,
) -> dict[str, Any]:
    """Run (or, with ``dry_run``, list) every task of every agent. Raises ``ValueError`` before running anything on a bad setup."""
    root = Path(workspaces)
    if not root.is_dir():
        raise ValueError(f"{root} does not exist: run `monte-neo bench prepare` first")
    if base_url:
        check_endpoint(base_url)
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
    broken: set[str] = set()  # an agent that failed once is not run on its other tasks: the cause is usually shared (login, model, server)
    for agent, task, cmd in plan:
        if agent in broken:
            continue
        if (task / "strategy.py").exists():
            skipped.append(str(task))
            continue
        if dry_run:
            done.append(f"{agent} {task.name}: {cmd}")
            continue
        env = {**os.environ, "PROMPT": (task / "PROMPT.md").read_text(encoding="utf-8")}
        env.update({k: v for k, v in AGENT_ENV.get(agent, {}).items() if k not in os.environ})
        if base_url:  # a local OpenAI-compatible server (Ollama: http://localhost:11434/v1); the key is a placeholder there
            env.update({"OPENAI_BASE_URL": base_url, "OPENAI_API_KEY": api_key or env.get("OPENAI_API_KEY") or "local"})
            if model:
                env["OPENAI_MODEL"] = model
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
            broken.add(agent)
            tip = hint_for(body)
            failed.append(f"{agent} {task.name} (exit {code}): {body.strip()[-400:] or 'no output'}" + (f"\n  -> {tip}" if tip else ""))
    return {"ran": done, "skipped": skipped, "failed": failed, "dry_run": dry_run}
