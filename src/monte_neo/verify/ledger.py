"""Trial ledger: how many variants were tried on this data, counted instead of declared.

Selection bias is the quietest way a backtest lies: an agent tries 300 variants over three days and
reports the best one as if it were the only one. The ledger is an append-only file in the project
(``.monte-neo/ledger.jsonl``) where every verification records which variant it saw. The number of
distinct variants on the same data is the ``n_trials`` the Deflated Sharpe needs.

* A variant is the **normalised syntax tree** of the strategy (comments, docstrings, formatting and
  line numbers do not make a new variant) or, for a positions file, the hash of the positions.
* Entries are hash-chained: editing or deleting an old line breaks every later hash, and the
  certificate says so.
"""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_PATH = Path(".monte-neo") / "ledger.jsonl"
GENESIS = "0" * 64


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _Strip(ast.NodeTransformer):
    """Remove docstrings so that documentation does not make a new variant."""

    def _body(self, node: Any) -> Any:
        self.generic_visit(node)
        body = node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
        return node

    visit_FunctionDef = _body  # noqa: N815
    visit_AsyncFunctionDef = _body  # noqa: N815
    visit_ClassDef = _body  # noqa: N815
    visit_Module = _body  # noqa: N815


def variant_id(source: str | None, positions: np.ndarray | None = None) -> str | None:
    """Stable id of a strategy variant: its normalised syntax tree, or the hash of its positions."""
    if source:
        try:
            tree = _Strip().visit(ast.parse(source))
            return "ast:" + _sha(ast.dump(tree, annotate_fields=False, include_attributes=False).encode())[:16]
        except SyntaxError:
            return "src:" + _sha(source.encode())[:16]
    if positions is not None:
        return "pos:" + _sha(np.ascontiguousarray(positions).tobytes())[:16]
    return None


class Ledger:
    """An append-only, hash-chained list of verified variants."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_PATH

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    out.append({"_broken": line[:80]})
        return out

    @staticmethod
    def _hash(prev: str, body: dict[str, Any]) -> str:
        return _sha((prev + json.dumps(body, sort_keys=True, separators=(",", ":"))).encode())

    def check(self) -> dict[str, Any]:
        """Is the chain intact? ``{"ok", "entries", "problem"}``."""
        entries = self.entries()
        prev = GENESIS
        for i, entry in enumerate(entries):
            if "_broken" in entry:
                return {"ok": False, "entries": len(entries), "problem": f"line {i + 1} is not valid JSON"}
            body = {k: v for k, v in entry.items() if k != "hash"}
            if entry.get("prev") != prev or entry.get("hash") != self._hash(prev, body):
                return {"ok": False, "entries": len(entries), "problem": f"entry {i + 1} does not match the chain (edited or removed lines)"}
            prev = entry["hash"]
        return {"ok": True, "entries": len(entries), "problem": None}

    def variants(self, data_id: str) -> set[str]:
        """Distinct variants already verified on this data."""
        return {e["variant"] for e in self.entries() if e.get("data") == data_id and "variant" in e}

    def count_with(self, variant: str | None, data_id: str) -> int:
        """Variants on this data including the one being verified now."""
        known = self.variants(data_id)
        if variant:
            known = known | {variant}
        return max(1, len(known))

    def record(self, *, variant: str | None, data_id: str, sharpe: float, verdict: str, certificate_id: str) -> dict[str, Any]:
        """Append one entry and return it."""
        entries = self.entries()
        prev = entries[-1].get("hash", GENESIS) if entries and "_broken" not in entries[-1] else GENESIS
        body = {
            "seq": len(entries) + 1,
            "prev": prev,
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "variant": variant,
            "data": data_id,
            "sharpe": round(float(sharpe), 6) if np.isfinite(sharpe) else None,
            "verdict": verdict,
            "certificate": certificate_id,
        }
        entry = {**body, "hash": self._hash(prev, body)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry


def ledger_row(counted: int, declared: int | None, chain: dict[str, Any], path: Path) -> dict[str, Any]:
    """Check row ``trial_ledger``: the counted number of variants against the declared one."""
    from monte_neo.verify.checks import check

    details = {"counted": counted, "declared": declared, "entries": chain["entries"], "chain_ok": chain["ok"], "path": str(path)}
    if not chain["ok"]:
        return check("trial_ledger", "statistics", "fail", f"the trial ledger was changed: {chain['problem']}", details)
    if declared is not None and declared < counted:
        return check(
            "trial_ledger", "statistics", "warn",
            f"n_trials was declared as {declared} but the ledger counts {counted} variants tried on this data: the larger number is used",
            details,
        )
    return check("trial_ledger", "statistics", "pass", f"{counted} variant(s) tried on this data (counted by the ledger)", details)


__all__ = ["DEFAULT_PATH", "Ledger", "ledger_row", "variant_id"]
