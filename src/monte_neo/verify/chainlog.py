"""An append-only, hash-chained JSON-lines file: editing or removing an old line breaks every later hash."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


def _hash(prev: str, body: dict[str, Any]) -> str:
    return hashlib.sha256((prev + json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)).encode()).hexdigest()


class ChainLog:
    """Entries ``{seq, prev, at, ...fields, hash}``; the hash covers everything but itself and the previous hash."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    out.append({"_broken": line[:80]})
        return out

    def check(self) -> dict[str, Any]:
        """``{"ok", "entries", "problem"}``."""
        entries = self.entries()
        prev = GENESIS
        for i, entry in enumerate(entries):
            if "_broken" in entry:
                return {"ok": False, "entries": len(entries), "problem": f"line {i + 1} is not valid JSON"}
            body = {k: v for k, v in entry.items() if k != "hash"}
            if entry.get("prev") != prev or entry.get("hash") != _hash(prev, body):
                return {"ok": False, "entries": len(entries), "problem": f"entry {i + 1} does not match the chain (edited or removed lines)"}
            prev = entry["hash"]
        return {"ok": True, "entries": len(entries), "problem": None}

    def append(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Add one entry (refused when the chain is already broken) and return it."""
        state = self.check()
        if not state["ok"]:
            raise ValueError(f"{self.path} is not intact: {state['problem']}")
        entries = self.entries()
        prev = entries[-1]["hash"] if entries else GENESIS
        body = {"seq": len(entries) + 1, "prev": prev, "at": datetime.now(UTC).isoformat(timespec="microseconds"), **fields}
        entry = {**body, "hash": _hash(prev, body)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True, default=str) + "\n")
        return entry


__all__ = ["GENESIS", "ChainLog"]
