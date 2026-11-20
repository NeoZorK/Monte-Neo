"""Forward journal: a hash-chained record of what a frozen rule *would have done* on data that arrived after it was frozen.

Nothing here trades: there are no orders, no keys and no account. The journal appends one line per new bar of the data you give it:
the position the frozen rule takes from the data up to that bar only (the table is cut at the bar before the rule sees it) and the return
of the previous position over the bar. The first line fixes the start; history that is rewritten later no longer matches the hash of the first
rows and is refused. A bar recorded long after it closed is flagged ``late``. Costs are not applied: they follow from the recorded positions.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.research.candidate import frozen_source
from monte_neo.research.project import ResearchProject, _model, _returns
from monte_neo.verify.chainlog import ChainLog
from monte_neo.verify.ingest import load_ohlcv
from monte_neo.verify.sealed_holdout import _data_id

SCHEMA = "research-forward/1"
MAX_BARS_PER_RUN = 500
LATE_AFTER = pd.Timedelta(days=3)


def _stamps(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["timestamp"], utc=True) if "timestamp" in df.columns else pd.Series(np.arange(len(df)), index=df.index)


def _bars(df: pd.DataFrame) -> list[Any]:
    return sorted(_stamps(df).drop_duplicates().tolist())


def _upto(df: pd.DataFrame, stamp: Any) -> pd.DataFrame:
    return df[(_stamps(df) <= stamp).to_numpy()].reset_index(drop=True)


class ForwardJournal:
    """The forward journal of a project's frozen candidate."""

    def __init__(self, project: ResearchProject) -> None:
        self.project = project
        self.log = ChainLog(project.path / "forward.jsonl")

    def _entries(self, kind: str) -> list[dict[str, Any]]:
        return [e for e in self.log.entries() if e.get("kind") == kind]

    def freeze(self, data: str | Path | pd.DataFrame) -> dict[str, Any]:
        """Fix the start: the frozen candidate, the data so far (hash of its rows) and the last bar already seen.

        Raises:
            ValueError: Nothing frozen in the project, or the journal already has a start.
        """
        with self.project.lock.held():
            fz = self.project._entries("freeze")
            if not fz:
                raise ValueError("nothing is frozen: freeze a validated candidate (research holdout) before recording it forward")
            if self.log.entries():
                raise ValueError("the forward journal already has a start: a rule is recorded forward from one fixed point")
            df = load_ohlcv(data)
            bars = _bars(df)
            c = self.project._candidate(fz[0]["candidate"])
            from monte_neo.verify.ledger import variant_id

            return self.log.append({"kind": "forward_freeze", "schema": SCHEMA, "candidate": c.id, "variant": variant_id(frozen_source(c.source, c.params)), "rows": len(df),
                                    "prefix_sha256": _data_id(df), "start": str(bars[-1]) if "timestamp" in df.columns else int(bars[-1]), "bars_at_start": len(bars)})

    def record(self, data: str | Path | pd.DataFrame, *, model: ExecutionModel | None = None, now: datetime | None = None) -> dict[str, Any]:
        """Append every bar after the last recorded one; the same command after any gap catches up. Returns ``{"new", "last", "late"}``.

        Raises:
            ValueError: No start, the history before the start changed, the rule changed, or more than 500 bars are missing.
        """
        with self.project.lock.held():
            starts = self._entries("forward_freeze")
            if not starts:
                raise ValueError("the forward journal has no start: run `research forward freeze` first")
            chain = self.log.check()
            if not chain["ok"]:
                raise ValueError(f"the forward journal was changed: {chain['problem']}")
            st = starts[0]
            df = load_ohlcv(data)
            if len(df) < st["rows"] or _data_id(df.iloc[: st["rows"]]) != st["prefix_sha256"]:
                raise ValueError("the history before the start was rewritten: the forward record cannot continue on different data")
            c = self.project._candidate(st["candidate"])
            from monte_neo.verify.ledger import variant_id

            if variant_id(frozen_source(c.source, c.params)) != st["variant"]:
                raise ValueError("the frozen rule changed after the forward start")
            bars = _bars(df)
            done = [e["ts"] for e in self._entries("bar")]
            last = done[-1] if done else st["start"]
            cut: Any = pd.Timestamp(last) if "timestamp" in df.columns else int(last)
            todo = [b for b in bars if b > cut]
            if len(todo) > MAX_BARS_PER_RUN:
                raise ValueError(f"{len(todo)} bars are missing; record at least every {MAX_BARS_PER_RUN} bars so that every position comes from the data of its day")
            fn, m, late = c.signal_fn(), _model(model), 0
            stamp_now = pd.Timestamp(now or datetime.now(UTC))
            stamp_now = stamp_now.tz_localize("UTC") if stamp_now.tzinfo is None else stamp_now
            for b in todo:
                part = _upto(df, b)
                pos = np.asarray(fn(part.copy()), dtype=float).reshape(-1)
                ret = float(_returns(fn, part, m)[-1]) if len(part) > 2 else 0.0
                ts = str(b) if "timestamp" in df.columns else int(b)
                is_late = bool("timestamp" in df.columns and stamp_now.tz_convert("UTC") - b > LATE_AFTER + pd.Timedelta(days=1))
                late += int(is_late)
                digest = hashlib.sha256(np.ascontiguousarray(part[["open", "high", "low", "close"]].tail(5).to_numpy(dtype=float)).tobytes()).hexdigest()[:16]
                self.log.append({"kind": "bar", "ts": ts, "position": float(pos[-1]) if pos.size else 0.0, "return": ret, "inputs": digest, "late": is_late})
            return {"new": len(todo), "last": (str(todo[-1]) if "timestamp" in df.columns else todo[-1]) if todo else last, "late": late}

    def status(self) -> dict[str, Any]:
        starts, bars = self._entries("forward_freeze"), self._entries("bar")
        chain = self.log.check()
        rets = np.array([b.get("return", 0.0) for b in bars])
        return {"started": bool(starts), "start": starts[0]["start"] if starts else None, "candidate": starts[0]["candidate"] if starts else None, "chain_ok": chain["ok"],
                "chain_problem": chain["problem"], "bars": len(bars), "last": bars[-1]["ts"] if bars else None, "late_bars": sum(1 for b in bars if b.get("late")),
                "gross_return": float(np.prod(1.0 + rets) - 1.0) if rets.size else 0.0, "held_bars": sum(1 for b in bars if b.get("position", 0) != 0)}


__all__ = ["MAX_BARS_PER_RUN", "SCHEMA", "ForwardJournal"]
