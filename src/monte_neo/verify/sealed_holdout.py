"""A sealed holdout that opens exactly once: the only source of D4 (out of sample) in the ARL depth.

Protocol, recorded in a hash-chained file (:class:`~monte_neo.verify.chainlog.ChainLog`), so no entry can be removed:

1. ``freeze``: the data (hash), the strategy variant (hash of its source) and the cut after which the data is sealed are
   written down *before* anyone looks at the sealed part. Everything that chose the parameters used only the data before the cut.
2. ``open``: the frozen strategy runs on the sealed part once; the resulting check rows are the D4 evidence. The variant must
   be the frozen one (a changed strategy cannot use the seal).
3. A second ``open`` does not return a result. It writes a ``reopen`` entry with the reason and the evidence becomes invalid
   for good: D4 is 0 at every level, permanently, and the file shows why. A new strategy needs new, unseen data.

The file protects against honest mistakes and over-eager agents; like the other ledgers it cannot hide itself from a
process that may rewrite the disk (run the verifier where the agent cannot write ``.monte-neo``).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.chainlog import ChainLog
from monte_neo.verify.ledger import variant_id

DEFAULT_PATH = Path(".monte-neo") / "sealed_holdout.jsonl"
SCHEMA = "sealed-holdout/1"


def _data_id(df: pd.DataFrame) -> str:
    cols = [c for c in ("open", "high", "low", "close") if c in df.columns]
    return hashlib.sha256(np.ascontiguousarray(df[cols].to_numpy(dtype=np.float64)).tobytes()).hexdigest()[:16]


def _stamps(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["timestamp"]) if "timestamp" in df.columns else pd.Series(pd.RangeIndex(len(df)))


class SealedHoldout:
    """Freeze, open once, and read the evidence back."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.log = ChainLog(path or DEFAULT_PATH)

    def freeze(self, df: pd.DataFrame, source: str, *, fraction: float = 0.2, n_trials: int = 1, cut: Any = None) -> dict[str, Any]:
        """Seal the last ``fraction`` of the data (or everything from ``cut``, a date or bar number fixed earlier) for the strategy whose source is ``source``.

        Raises:
            ValueError: Already frozen, a fraction outside 0.05..0.5, or ``n_trials`` below 1.
        """
        if self.log.entries():
            raise ValueError(f"{self.log.path} already holds a freeze: a holdout is sealed once per strategy and data set")
        if not 0.05 <= fraction <= 0.5 or n_trials < 1:
            raise ValueError("fraction must be between 0.05 and 0.5 and n_trials >= 1")
        stamps = np.sort(_stamps(df).unique())
        if cut is None:
            cut = stamps[int(len(stamps) * (1.0 - fraction))]
        else:
            col = _stamps(df)
            if not bool((col >= (pd.Timestamp(cut) if pd.api.types.is_datetime64_any_dtype(col) else int(cut))).any()):
                raise ValueError("the cut leaves no sealed bars")
        return self.log.append({"kind": "freeze", "data": _data_id(df), "bars": len(df), "variant": variant_id(source), "cut": str(cut),
                                "fraction": fraction, "n_trials": int(n_trials)})

    def _state(self) -> dict[str, Any]:
        chain = self.log.check()
        entries = self.log.entries()
        if not chain["ok"]:
            return {"ok": False, "reason": f"the holdout file was changed: {chain['problem']}", "entries": entries}
        if not entries or entries[0].get("kind") != "freeze":
            return {"ok": False, "reason": "the holdout was never frozen", "entries": entries}
        return {"ok": True, "reason": None, "entries": entries}

    def open(self, df: pd.DataFrame, signal_fn: Any, source: str, *, model: ExecutionModel | None = None) -> dict[str, Any]:
        """Run the frozen strategy on the sealed part. The first call returns the evidence; later calls spoil it.

        Raises:
            ValueError: Not frozen, the data or the strategy differ from the frozen ones.
        """
        from monte_neo.verify import verify_strategy

        state = self._state()
        if not state["ok"]:
            raise ValueError(state["reason"])
        freeze = state["entries"][0]
        if _data_id(df) != freeze["data"] or len(df) != freeze["bars"]:
            raise ValueError("this is not the data the holdout was frozen on")
        if variant_id(source) != freeze["variant"]:
            raise ValueError("the strategy changed after the freeze: it cannot use the seal")
        if any(e.get("kind") == "open" for e in state["entries"]):
            self.log.append({"kind": "reopen", "reason": "the sealed holdout was opened more than once"})
            return self.evidence()
        stamps = _stamps(df)
        cut = pd.Timestamp(freeze["cut"]) if "timestamp" in df.columns else int(freeze["cut"])
        mask = np.asarray(stamps >= cut)
        positions = np.asarray(signal_fn(df.copy()), dtype=float).reshape(-1)
        report = verify_strategy(df[mask].reset_index(drop=True), signals=positions[mask], model=model, n_trials=int(freeze["n_trials"]), probe_checks=4)
        rows = [{"id": c["id"], "status": c["status"], "category": c["category"], "summary": c["summary"], "details": c.get("details") or {}} for c in report["checks"]]
        self.log.append({"kind": "open", "certificate_id": report["certificate_id"], "verdict": report["verdict"], "checks": rows})
        return self.evidence()

    def evidence(self) -> dict[str, Any]:
        """``{"schema", "valid", "opens", "reason", "checks", "certificate_id"}``; invalid means D4 is 0 at every level."""
        state = self._state()
        entries = state["entries"]
        opens = [e for e in entries if e.get("kind") == "open"]
        reopened = any(e.get("kind") == "reopen" for e in entries)
        base = {"schema": SCHEMA, "opens": len(opens), "checks": opens[0]["checks"] if opens else [], "certificate_id": opens[0]["certificate_id"] if opens else None}
        if not state["ok"]:
            return {**base, "valid": False, "reason": state["reason"]}
        if reopened or len(opens) > 1:
            return {**base, "valid": False, "reason": "the sealed holdout was opened more than once (see the reopen entry in the holdout file)"}
        if not opens:
            return {**base, "valid": False, "reason": "the sealed holdout is frozen but was not opened yet"}
        return {**base, "valid": True, "reason": None}


__all__ = ["DEFAULT_PATH", "SCHEMA", "SealedHoldout"]
