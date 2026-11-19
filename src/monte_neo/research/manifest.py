"""The project manifest, atomic writes and a lock, so a long search survives a crash, a power cut or a second terminal.

* ``manifest.json`` holds the fixed facts of the project (split, data hash, policy, profile, grammar hash) and the mutable ones (stage,
  progress). It is replaced atomically (write to a temporary file, flush, ``os.replace``), never edited in place.
* ``.lock`` is held while a command writes to the project. It carries the process id; a lock whose process is gone is taken over.
* The hash-chained record (``research.jsonl``) stays the authority: the manifest is a convenience and is checked against it.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "research-manifest/1"
MANIFEST = "manifest.json"
LOCK = ".lock"
STAGES = ("init", "screening", "promoted", "validated", "frozen", "holdout_opened", "reported")
DEFAULT_POLICY: dict[str, Any] = {
    "alpha": 0.05,            # family-wise level of the Romano-Wolf stepdown
    "spa_level": 0.10,        # the family SPA must be at or below this for the gate
    "min_effective_n": 30,    # effective independent observations a candidate needs
    "power": 0.80,            # power used for the minimum detectable Sharpe
    "cluster_corr": 0.95,     # |correlation| at which two candidates count as one independent try
    "fdr_q": 0.10,            # false discovery rate level
}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def atomic_write(path: Path, text: str) -> None:
    """Write ``text`` so that a reader sees the old file or the new one, never half of it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def read_manifest(root: Path) -> dict[str, Any] | None:
    f = root / MANIFEST
    if not f.is_file():
        return None
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{f} is damaged ({exc.msg}); the hash-chained record is intact, restore the manifest from it with `research status --repair`") from exc
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"{f}: unknown manifest schema {doc.get('schema')!r}")
    return doc


def write_manifest(root: Path, doc: dict[str, Any]) -> None:
    atomic_write(root / MANIFEST, json.dumps({**doc, "schema": SCHEMA, "updated_at": now()}, indent=1, sort_keys=True, default=str) + "\n")


def new_manifest(*, name: str, data_sha: str, rows: int, bars: dict[str, int], splits: dict[str, str], policy: dict[str, Any] | None,
                 profile: str | None, grammar: dict[str, Any] | None, data_path: str | None) -> dict[str, Any]:
    pol = {**DEFAULT_POLICY, **(policy or {})}
    unknown = set(policy or {}) - set(DEFAULT_POLICY)
    if unknown:
        raise ValueError(f"unknown policy keys: {', '.join(sorted(unknown))}")
    return {"schema": SCHEMA, "name": name, "created_at": now(), "stage": "init", "data": {"sha256": data_sha, "rows": rows, "path": data_path}, "bars": bars,
            "splits": splits, "policy": pol, "profile": profile, "grammar": grammar, "progress": None}


class ProjectLock:
    """Exclusive lock on a project folder, re-entrant inside one process, taken over when its owner is gone."""

    def __init__(self, root: Path, timeout: float = 10.0) -> None:
        self.path, self.timeout, self.depth = root / LOCK, timeout, 0

    @staticmethod
    def _alive(pid: int) -> bool:
        if pid == os.getpid():
            return True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    def owner(self) -> int | None:
        try:
            return int(self.path.read_text(encoding="utf-8").split()[0])
        except (OSError, ValueError, IndexError):
            return None

    def acquire(self) -> None:
        if self.depth:
            self.depth += 1
            return
        end = time.monotonic() + self.timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                pid = self.owner()
                if pid is None or not self._alive(pid):  # a crashed run left it behind
                    with contextlib.suppress(OSError):
                        self.path.unlink()
                    continue
                if time.monotonic() >= end:
                    raise ValueError(f"the project is locked by process {pid}: another research command is writing to it; wait for it or stop it") from None
                time.sleep(0.05)
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"{os.getpid()} {now()}\n")
            self.depth = 1
            return

    def release(self) -> None:
        self.depth -= 1
        if self.depth == 0:
            with contextlib.suppress(OSError):
                self.path.unlink()

    @contextlib.contextmanager
    def held(self) -> Iterator[None]:
        self.acquire()
        try:
            yield
        finally:
            self.release()


__all__ = ["DEFAULT_POLICY", "LOCK", "MANIFEST", "SCHEMA", "STAGES", "ProjectLock", "atomic_write", "new_manifest", "now", "read_manifest", "write_manifest"]
