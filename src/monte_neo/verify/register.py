"""Pre-registration: a hypothesis is written down, with the hash of the code, before the test is run.

``.monte-neo/registrations.jsonl`` is hash-chained, so a hypothesis cannot be changed or removed after the
result is known. A certificate that names a registration says whether the verified code is the registered one
and whether the registration came before the first verification of that code in the trial ledger.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from monte_neo.verify.chainlog import ChainLog
from monte_neo.verify.ledger import variant_id

DEFAULT_PATH = Path(".monte-neo") / "registrations.jsonl"


def _spec_hash(hypothesis: str, variant: str | None, params: dict[str, Any] | None, n_trials: int | None) -> str:
    body = json.dumps({"hypothesis": hypothesis, "variant": variant, "params": params or {}, "n_trials": n_trials}, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


class Registry:
    def __init__(self, path: str | Path | None = None) -> None:
        self.log = ChainLog(path or DEFAULT_PATH)

    def register(
        self, hypothesis: str, *, source: str | None = None, params: dict[str, Any] | None = None, n_trials: int | None = None,
        data_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Record the hypothesis; ``source`` is the code to be tested (its normalised hash is stored, not the code)."""
        if not hypothesis.strip():
            raise ValueError("a hypothesis is a sentence: what do you expect to find, and why")
        variant = variant_id(source) if source else None
        entry = self.log.append({
            "hypothesis": hypothesis.strip(), "variant": variant, "params": params or {}, "planned_trials": n_trials,
            "data": data_sha256, "spec": _spec_hash(hypothesis.strip(), variant, params, n_trials),
        })
        entry["id"] = f"reg-{entry['seq']}-{entry['hash'][:8]}"
        return entry

    def find(self, reg_id: str) -> dict[str, Any] | None:
        for entry in self.log.entries():
            if "hash" in entry and f"reg-{entry.get('seq')}-{entry['hash'][:8]}" == reg_id:
                return entry
        return None


def registration_row(
    reg_id: str, registry: Registry, variant: str | None, ledger_first_at: str | None, *, ledger_used: bool = False
) -> dict[str, Any]:
    """Check row ``preregistration`` (always ``info``: it informs the reader and never moves the verdict)."""
    from monte_neo.verify.checks import check

    chain = registry.log.check()
    entry = registry.find(reg_id) if chain["ok"] else None
    if not chain["ok"]:
        return check("preregistration", "statistics", "info", f"registrations file was changed: {chain['problem']}", {"id": reg_id, "chain_ok": False})
    if entry is None:
        return check("preregistration", "statistics", "info", f"registration {reg_id} not found", {"id": reg_id, "found": False})
    same = entry.get("variant") is None or entry.get("variant") == variant
    before = ledger_first_at is None or datetime.fromisoformat(entry["at"]) < datetime.fromisoformat(ledger_first_at)
    details = {"id": reg_id, "found": True, "registered_at": entry["at"], "same_code": bool(same), "before_first_verification": bool(before),
               "hypothesis": entry["hypothesis"]}
    if same and before and not ledger_used:
        return check("preregistration", "statistics", "info", f"pre-registered at {entry['at']}; run with the trial ledger to prove it came before the first verification", details)
    if same and before:
        return check("preregistration", "statistics", "info", f"pre-registered at {entry['at']}: the hypothesis was written before the first verification of this code", details)
    why = ("the verified code is not the registered code" if not same else "the registration is later than the first verification of this code")
    return check("preregistration", "statistics", "info", f"registration {reg_id} does NOT protect this result: {why}", details)


__all__ = ["DEFAULT_PATH", "Registry", "registration_row"]
