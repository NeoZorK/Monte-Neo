"""Workspaces for a public Honesty Bench run.

``prepare`` copies each task's ``data.csv`` and ``PROMPT.md`` into one clean
workspace per agent and task. Task ids are replaced by neutral aliases
(``task-1`` …) drawn at random, because names such as ``costs-trap`` would give
the answer away. The alias map stays in the bench directory next to
``answer_key.json``; neither is copied into a workspace.

``collect`` copies each agent's ``strategy.py`` and ``claim.json`` (plus any
session transcript) back into ``submissions/<agent>/<task>/`` for scoring.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
from pathlib import Path
from typing import Any

ALIASES_FILE = "aliases.json"
DATA_HASHES_FILE = "DATA_SHA256"
TRANSCRIPT_GLOBS = ("transcript*", "*.log", "*.jsonl")
_AGENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _tasks(root: Path) -> list[str]:
    tasks = sorted(p.name for p in (root / "tasks").glob("*/") if (p / "data.csv").is_file())
    if not tasks:
        raise FileNotFoundError(f"no tasks under {root / 'tasks'}; run `monte-neo bench init` first")
    return tasks


def prepare(root: str | Path, workspaces: str | Path, agents: list[str], *, rng: random.Random | None = None) -> dict[str, Any]:
    """Create ``workspaces/<agent>/<alias>/`` with only ``data.csv`` and ``PROMPT.md``."""
    base, out = Path(root).resolve(), Path(workspaces).resolve()
    if not agents:
        raise ValueError("give at least one agent name")
    bad = [a for a in agents if not _AGENT_NAME.match(a)]
    if bad:
        raise ValueError(f"agent names may use letters, digits, '.', '_' and '-' only: {bad}")
    if out == base or base in out.parents:
        raise ValueError("create the workspaces outside the bench directory, so agents cannot reach the answer key")
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} is not empty")
    tasks = _tasks(base)
    order = list(range(1, len(tasks) + 1))
    (rng or random.SystemRandom()).shuffle(order)
    aliases = {f"task-{n}": task for n, task in zip(order, tasks, strict=True)}
    hashes = {}
    for task in tasks:
        hashes[task] = hashlib.sha256((base / "tasks" / task / "data.csv").read_bytes()).hexdigest()
    for agent in agents:
        for alias, task in aliases.items():
            ws = out / agent / alias
            ws.mkdir(parents=True)
            shutil.copyfile(base / "tasks" / task / "data.csv", ws / "data.csv")
            shutil.copyfile(base / "tasks" / task / "PROMPT.md", ws / "PROMPT.md")
    (base / ALIASES_FILE).write_text(json.dumps(aliases, indent=2, sort_keys=True), encoding="utf-8")
    (base / DATA_HASHES_FILE).write_text("".join(f"{h}  tasks/{t}/data.csv\n" for t, h in sorted(hashes.items())), encoding="utf-8")
    return {"workspaces": str(out), "agents": list(agents), "tasks": len(tasks), "aliases_file": str(base / ALIASES_FILE)}


def collect(root: str | Path, workspaces: str | Path) -> dict[str, Any]:
    """Copy agent outputs from the workspaces into ``submissions/<agent>/<task>/``."""
    base, src = Path(root), Path(workspaces)
    aliases_path = base / ALIASES_FILE
    if not aliases_path.is_file():
        raise FileNotFoundError(f"{aliases_path} not found; run `monte-neo bench prepare` first")
    aliases: dict[str, str] = json.loads(aliases_path.read_text(encoding="utf-8"))
    collected, missing = [], []
    for agent_dir in sorted(p for p in src.iterdir() if p.is_dir()):
        for alias, task in sorted(aliases.items()):
            ws = agent_dir / alias
            if not (ws / "strategy.py").is_file():
                missing.append(f"{agent_dir.name}/{alias} ({task})")
                continue
            dest = base / "submissions" / agent_dir.name / task
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ws / "strategy.py", dest / "strategy.py")
            if (ws / "claim.json").is_file():
                shutil.copyfile(ws / "claim.json", dest / "claim.json")
            for pattern in TRANSCRIPT_GLOBS:
                for f in ws.glob(pattern):
                    shutil.copyfile(f, dest / f.name)
            collected.append(f"{agent_dir.name}/{task}")
    return {"collected": collected, "missing": missing}


__all__ = ["ALIASES_FILE", "DATA_HASHES_FILE", "collect", "prepare"]
