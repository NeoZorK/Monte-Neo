"""Append-only, hash-chained evidence journal (JSON lines).

Every line is ``{"seq", "ts", "kind", "body", "prev", "hash"}`` where ``hash = sha256(prev + canonical(entry without hash))``.
A changed, removed or reordered line breaks the chain, and :func:`verify` names the first bad line. Writes are
fsync'ed under an exclusive lock, so a power cut leaves at most one incomplete last line, which :func:`verify`
reports and :meth:`Journal.repair_tail` moves aside (never silently drops).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

try:  # POSIX file lock; on other platforms the lock is skipped (single writer assumed)
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

GENESIS = "0" * 64


def canonical(obj: Any) -> str:
    """Canonical JSON: sorted keys, no spaces; the same object always gives the same text."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _hash(prev: str, entry: dict[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256((prev + canonical(body)).encode()).hexdigest()


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Journal:
    """One journal file."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def entries(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return iter(())
        return (json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip())

    def head(self) -> dict[str, Any]:
        last = None
        for last in self.entries():
            pass
        return {"seq": last["seq"], "hash": last["hash"]} if last else {"seq": -1, "hash": GENESIS}

    def append(self, kind: str, body: dict[str, Any]) -> dict[str, Any]:
        """Append one entry under an exclusive lock and fsync it; returns the entry."""
        lock = self.path.with_suffix(".lock")
        with open(lock, "w") as lk:
            if fcntl is not None:
                fcntl.flock(lk, fcntl.LOCK_EX)
            h = self.head()
            entry: dict[str, Any] = {"seq": h["seq"] + 1, "ts": utc_now(), "kind": kind, "body": body, "prev": h["hash"]}
            entry["hash"] = _hash(h["hash"], entry)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(canonical(entry) + "\n")
                f.flush()
                os.fsync(f.fileno())
            return entry

    def find(self, kind: str, **match: Any) -> list[dict[str, Any]]:
        return [e for e in self.entries() if e["kind"] == kind and all(e["body"].get(k) == v for k, v in match.items())]

    def repair_tail(self) -> Path | None:
        """Move an incomplete last line (power cut during a write) to ``<journal>.broken-<ts>``; returns that file or None."""
        if not self.path.exists():
            return None
        lines = self.path.read_text(encoding="utf-8").splitlines(keepends=True)
        if not lines:
            return None
        try:
            json.loads(lines[-1])
            return None
        except json.JSONDecodeError:
            aside = self.path.with_name(f"{self.path.name}.broken-{int(time.time())}")
            aside.write_text(lines[-1], encoding="utf-8")
            self.path.write_text("".join(lines[:-1]), encoding="utf-8")
            return aside


def verify(path: Path | str) -> dict[str, Any]:
    """Check the whole chain: ``{"ok", "entries", "head", "problem"}``."""
    prev, n, seq = GENESIS, 0, -1
    p = Path(path)
    if not p.exists():
        return {"ok": True, "entries": 0, "head": GENESIS, "problem": None}
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            return {"ok": False, "entries": n, "head": prev, "problem": f"line {i} is not valid JSON (incomplete write?)"}
        if not isinstance(e, dict) or e.get("prev") != prev or e.get("seq") != seq + 1 or e.get("hash") != _hash(prev, e):
            seq_txt = e.get("seq") if isinstance(e, dict) else "?"
            return {"ok": False, "entries": n, "head": prev, "problem": f"line {i} (seq {seq_txt}) does not match the chain"}
        prev, seq, n = e["hash"], e["seq"], n + 1
    return {"ok": True, "entries": n, "head": prev, "problem": None}
