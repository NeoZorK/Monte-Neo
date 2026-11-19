"""An honest search project: fixed split, ledger of every variant, pre-registered batches, one sealed holdout.

The order of events is written into a hash-chained file (``research.jsonl``) and cannot be rearranged afterwards:

1. ``create``: the data (hash), the cut dates and the number of bars of each part are recorded before any candidate runs.
2. ``screen``: candidates run on the **discovery** part only. The code is handed a table that ends at the discovery cut, so it
   cannot read validation or holdout rows, and every variant (code hash and parameters) goes to the ledger, tried or not.
3. ``preregister``: the candidates to promote and the rule that chose them are written down *before* validation is read.
4. ``validate``: the batch runs on the **validation** part once. The statistics cover every promoted candidate of every batch
   (SPA, Reality Check, Romano-Wolf, the expected maximum Sharpe of luck). ``n_trials`` is the number of promoted candidates.
5. ``freeze`` one candidate (hash of code and parameters), then ``open_holdout`` once. A second opening spoils the holdout
   for good: D4 of the ARL depth is 0 at every level, permanently.
"""

from __future__ import annotations

import functools
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.research.candidate import Candidate, frozen_source
from monte_neo.research.family import family_rows, family_stats
from monte_neo.research.manifest import STAGES, ProjectLock, new_manifest, now, read_manifest, write_manifest
from monte_neo.research.splits import Splits, _stamps
from monte_neo.verify.chainlog import ChainLog
from monte_neo.verify.engine import simulate
from monte_neo.verify.ingest import load_ohlcv, resolve_positions
from monte_neo.verify.market import market_for
from monte_neo.verify.sealed_holdout import SealedHoldout, _data_id
from monte_neo.verify.stats import bar_returns, infer_periods_per_year, sharpe_per_bar

SCHEMA = "research-project/1"
SPA_LEVEL = 0.10
MAX_STORED_BARS = 50_000
from monte_neo.research.manifest import DEFAULT_POLICY  # noqa: E402


def _safe(cid: str) -> str:
    return cid.replace(":", "_")


def _model(model: ExecutionModel | None) -> ExecutionModel:
    return model or ExecutionModel(side_mode="long_short", warmup_bars=0)


def _returns(fn: Any, frame: pd.DataFrame, model: ExecutionModel) -> np.ndarray:
    """Per-bar returns of one candidate on ``frame``; element ``i`` belongs to time step ``i + 1`` (no warm-up cut)."""
    market = market_for(frame)
    values = market.read_values(fn, None)
    mode = resolve_positions(values, "auto")
    return bar_returns(simulate(market.ohlc, market.positions(values, mode, model)[0], model)["equity"], start=0)


def _ppy(df: pd.DataFrame) -> float:
    return float(infer_periods_per_year(pd.Series(_stamps(df).unique()))) if "timestamp" in df.columns else 252.0


def _locked(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Run a writing method while holding the project lock."""
    @functools.wraps(fn)
    def wrapper(self: ResearchProject, *a: Any, **k: Any) -> Any:
        with self.lock.held():
            return fn(self, *a, **k)
    return wrapper


def list_sha(ids: list[str]) -> str:
    """Hash of a batch list (order does not matter)."""
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


class ResearchProject:
    """Create with :meth:`create`, reopen with the constructor."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.lock = ProjectLock(self.path)
        self.log = ChainLog(self.path / "research.jsonl")
        self._heal()
        if not self.log.entries() or self.log.entries()[0].get("kind") != "init":
            raise ValueError(f"{self.path} is not a research project (create it first)")
        chain = self.log.check()
        if not chain["ok"]:
            raise ValueError(f"the project record was changed: {chain['problem']}")
        init = self.log.entries()[0]
        self.name: str = init["name"]
        self.splits = Splits(init["discovery_end"], init["validation_end"])
        self.data_id: str = init["data"]
        self.manifest = read_manifest(self.path)
        self.policy: dict[str, Any] = (self.manifest or {}).get("policy") or dict(DEFAULT_POLICY)
        self.profile: str | None = (self.manifest or {}).get("profile")

    def _heal(self) -> None:
        """A crash while a line was being written leaves a last line without its newline; it is not part of the record and is dropped."""
        f = self.log.path
        if not f.is_file():
            return
        raw = f.read_bytes()
        if raw and not raw.endswith(b"\n"):
            cut = raw.rfind(b"\n") + 1
            f.write_bytes(raw[:cut])
            (self.path / "healed.log").open("a", encoding="utf-8").write(f"{now()} dropped a half-written last line ({len(raw) - cut} bytes)\n")

    def _save(self, **fields: Any) -> None:
        """Update the mutable part of the manifest (stage moves forward only)."""
        if self.manifest is None:
            return
        stage = fields.pop("stage", None)
        if stage and STAGES.index(stage) > STAGES.index(self.manifest.get("stage", "init")):
            self.manifest["stage"] = stage
        self.manifest.update(fields)
        write_manifest(self.path, self.manifest)

    @classmethod
    def create(cls, path: str | Path, data: pd.DataFrame | str | Path, discovery_end: Any, validation_end: Any, *, name: str = "research",
               policy: dict[str, Any] | None = None, profile: str | None = None, grammar: dict[str, Any] | None = None) -> ResearchProject:
        """Record the split before any candidate runs.

        Raises:
            ValueError: The folder already holds a project, or the cuts do not fit the data.
        """
        root = Path(path)
        log = ChainLog(root / "research.jsonl")
        if log.entries():
            raise ValueError(f"{root} already holds a research project; a split is fixed once")
        df = load_ohlcv(data)
        sp = Splits.build(df, discovery_end, validation_end)
        if profile is not None:
            from monte_neo.profiles import get_profile

            get_profile(profile)  # fails early on an unknown id
        man = new_manifest(name=name, data_sha=_data_id(df), rows=len(df), bars=sp.bar_counts(df), splits=sp.as_dict(), policy=policy, profile=profile,
                           grammar=grammar, data_path=str(Path(data).resolve()) if isinstance(data, str | Path) else None)
        log.append({"kind": "init", "schema": SCHEMA, "name": name, "data": _data_id(df), "rows": len(df), "ppy": _ppy(df), **sp.as_dict(), "bars": sp.bar_counts(df),
                    "policy": man["policy"], "profile": profile})
        write_manifest(root, man)
        return cls(root)

    # ---- helpers -------------------------------------------------------------------------------------------------------
    def _entries(self, kind: str | None = None) -> list[dict[str, Any]]:
        es = self.log.entries()
        return [e for e in es if kind is None or e.get("kind") == kind]

    def _frame(self, data: pd.DataFrame | str | Path | None) -> pd.DataFrame:
        if data is None:
            hint = ((self.manifest or {}).get("data") or {}).get("path")
            if not hint or not Path(hint).is_file():
                raise ValueError("give the data file (--data): the project does not know where the data is")
            data = hint
        df = load_ohlcv(data)
        if _data_id(df) != self.data_id:
            raise ValueError("this is not the data the project was created with")
        return df

    def _candidate(self, cid: str) -> Candidate:
        f = self.path / "candidates" / f"{_safe(cid)}.json"
        if not f.is_file():
            raise ValueError(f"unknown candidate {cid}: it was never screened")
        d = json.loads(f.read_text(encoding="utf-8"))
        c = Candidate(d["source"], d["params"], d["label"])
        if c.id != cid:
            self._refuse("candidate", f"the stored code or parameters of {cid} were changed after screening")
        return c

    def _refuse(self, action: str, reason: str) -> None:
        """Write the refused attempt into the record (it shows in the report) and raise."""
        self.log.append({"kind": "refused", "action": action, "reason": reason})
        raise ValueError(reason)

    def screened(self) -> dict[str, dict[str, Any]]:
        """Every variant ever run on discovery: id -> its first ledger entry."""
        out: dict[str, dict[str, Any]] = {}
        for e in self._entries("screen"):
            out.setdefault(e["candidate"], e)
        return out

    def promoted(self) -> list[str]:
        """Candidates of all pre-registered batches, in order, each once."""
        seen: list[str] = []
        for e in self._entries("prereg"):
            seen += [c for c in e["candidates"] if c not in seen]
        return seen

    @property
    def n_trials(self) -> int:
        """All promoted candidates of all batches; it only grows."""
        return max(1, len(self.promoted()))

    # ---- 2. screening on discovery -------------------------------------------------------------------------------------
    @_locked
    def screen(self, data: pd.DataFrame | str | Path, candidates: list[Candidate], *, model: ExecutionModel | None = None) -> list[dict[str, Any]]:
        """Run candidates on the discovery part only; every one is written to the ledger (a repeat is not counted twice)."""
        df = self._frame(data)
        disc = self.splits.upto(df, "discovery")  # the candidate code gets nothing beyond this table
        del df
        ann = float(np.sqrt(_ppy(disc)))
        out: list[dict[str, Any]] = []
        known = self.screened()
        for c in candidates:
            if c.id in known:
                out.append({"candidate": c.id, "label": c.label, "sharpe_annual": known[c.id].get("sharpe_annual"), "repeat": True})
                continue
            cdir = self.path / "candidates"
            cdir.mkdir(parents=True, exist_ok=True)
            (cdir / f"{_safe(c.id)}.json").write_text(json.dumps({"source": c.source, "params": c.params, "label": c.label}, sort_keys=True), encoding="utf-8")
            row: dict[str, Any]
            try:
                r = _returns(c.signal_fn(), disc, _model(model))
                row = {"sharpe_annual": float(sharpe_per_bar(r) * ann), "bars": int(r.size), "error": None}
                if r.size <= MAX_STORED_BARS:  # kept to count the independent tries among everything that was screened
                    (self.path / "disc_returns").mkdir(parents=True, exist_ok=True)
                    np.save(self.path / "disc_returns" / f"{_safe(c.id)}.npy", r.astype(np.float32))
            except Exception as exc:  # a broken variant was still tried
                row = {"sharpe_annual": None, "bars": 0, "error": f"{type(exc).__name__}: {exc}"[:200]}
            self.log.append({"kind": "screen", "candidate": c.id, "label": c.label, "params": c.params, **row})
            out.append({"candidate": c.id, "label": c.label, **row})
            known[c.id] = {**row}
        self._save(stage="screening")
        return out

    def screen_grammar(self, data: pd.DataFrame | str | Path | None, grammar: Any, *, chunk: int = 25, model: ExecutionModel | None = None,
                       max_seconds: float | None = None, on_progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        """Screen every variant of a grammar on discovery, a chunk at a time, writing progress after each chunk.

        Variants already in the ledger are skipped, so the same command after a crash, a power cut or a time limit (``max_seconds``) goes on
        where it stopped. Returns ``{"done", "total", "new", "complete", "eta_seconds"}``.
        """
        import time

        cands = list(grammar.candidates())
        total, started = len(cands), time.monotonic()
        todo = [c for c in cands if c.id not in self.screened()]
        new = 0
        for i in range(0, len(todo), max(1, chunk)):
            if max_seconds is not None and time.monotonic() - started >= max_seconds:
                break
            part = todo[i:i + max(1, chunk)]
            new += len([r for r in self.screen(data, part, model=model) if not r.get("repeat")])
            elapsed = max(time.monotonic() - started, 1e-9)
            done = total - len(todo) + min(i + len(part), len(todo))
            left = total - done
            prog = {"phase": "screen", "done": done, "total": total, "updated_at": now(), "rate_per_s": new / elapsed, "eta_seconds": left / (new / elapsed) if new else None}
            self._save(progress=prog)
            if on_progress:
                on_progress(prog)
        done_now = len([c for c in cands if c.id in self.screened()])
        info = {"done": done_now, "total": total, "new": new, "complete": done_now == total, "eta_seconds": 0.0 if done_now == total else None}
        self._save(progress={"phase": "screen", "done": done_now, "total": total, "updated_at": now(), "eta_seconds": info["eta_seconds"]})
        return info

    def top_candidates(self, k: int, *, min_sharpe: float = 0.0) -> list[str]:
        """Not yet promoted candidates with the highest discovery Sharpe above ``min_sharpe``: a rule you can write into the batch."""
        done = set(self.promoted())
        rows = [(e["sharpe_annual"], cid) for cid, e in self.screened().items() if cid not in done and e.get("sharpe_annual") is not None and e["sharpe_annual"] > min_sharpe]
        return [cid for _, cid in sorted(rows, reverse=True)[: max(0, int(k))]]

    # ---- 3. pre-registration -------------------------------------------------------------------------------------------
    @_locked
    def preregister(self, ids: list[str], rule: str) -> int:
        """Write the batch to promote and the rule that chose it, before validation is read. Returns the batch number.

        Raises:
            ValueError: Empty batch, an unscreened or already promoted candidate, or no rule text.
        """
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("a batch needs at least one candidate, each listed once")
        if not rule.strip():
            raise ValueError("write the rule that chose this batch (for example 'top 5 by discovery Sharpe')")
        known, done = self.screened(), set(self.promoted())
        for cid in ids:
            if cid not in known:
                raise ValueError(f"candidate {cid} was not screened on discovery")
            if cid in done:
                raise ValueError(f"candidate {cid} was already promoted in an earlier batch")
        batch = len(self._entries("prereg")) + 1
        digest = list_sha(ids)
        self.log.append({"kind": "prereg", "batch": batch, "candidates": sorted(ids), "rule": rule.strip(), "screened_so_far": len(known), "list_sha256": digest})
        from monte_neo.research.manifest import atomic_write

        atomic_write(self.path / "batches" / f"batch{batch:03d}.json", json.dumps(
            {"batch": batch, "candidates": sorted(ids), "rule": rule.strip(), "list_sha256": digest, "written_at": now()}, indent=1, sort_keys=True) + "\n")
        self._save(stage="promoted")
        return batch

    def promote(self, *, top: int | None = None, ids: list[str] | None = None, rule: str | None = None, min_sharpe: float = 0.0) -> dict[str, Any]:
        """Pre-register the next batch: the ``top`` not yet promoted candidates by discovery Sharpe, or the listed ``ids``.

        The list and its hash are written (record and ``batches/batchNNN.json``) before validation can be read.
        """
        chosen = list(ids) if ids else (self.top_candidates(int(top), min_sharpe=min_sharpe) if top else [])
        if not chosen:
            raise ValueError("promote needs ids=[...] or top=K with at least one candidate above min_sharpe")
        text = rule or f"top {len(chosen)} by discovery Sharpe above {min_sharpe:g}"
        batch = self.preregister(chosen, text)
        return {"batch": batch, "candidates": sorted(chosen), "rule": text, "list_sha256": list_sha(chosen), "n_trials": self.n_trials}

    # ---- 4. validation -------------------------------------------------------------------------------------------------
    @_locked
    def validate(self, data: pd.DataFrame | str | Path, *, batch: int | None = None, model: ExecutionModel | None = None) -> dict[str, Any]:
        """Read validation once for a pre-registered batch; statistics cover the whole family of all batches so far.

        Raises:
            ValueError: No pre-registered batch waits, or the batch was already validated.
        """
        preregs = {e["batch"]: e for e in self._entries("prereg")}
        reads = {e["batch"] for e in self._entries("validation_read")}
        if batch is None:
            waiting = [b for b in preregs if b not in reads]
            if not waiting:
                self._refuse("validate", "no pre-registered batch waits for validation (promote one first)")
            batch = waiting[0]
        if batch not in preregs:
            self._refuse("validate", f"batch {batch} was not pre-registered")
        if batch in reads:
            self._refuse("validate", f"batch {batch} was already validated: validation is read once per batch")
        bf = self.path / "batches" / f"batch{batch:03d}.json"
        want = preregs[batch].get("list_sha256")
        if want is not None:
            try:
                on_disk = json.loads(bf.read_text(encoding="utf-8")) if bf.is_file() else None
            except json.JSONDecodeError:
                on_disk = None
            if on_disk is None or list_sha(on_disk.get("candidates", [])) != want or on_disk.get("list_sha256") != want:
                self._refuse("validate", f"batch {batch}: the pre-registered list was changed or removed (batches/batch{batch:03d}.json does not match the record)")
        df = self._frame(data)
        frame = self.splits.upto(df, "validation")
        n_disc = self.splits.bar_counts(df)["discovery"]
        del df
        self.log.append({"kind": "validation_read", "batch": batch})  # written before the numbers exist
        m = _model(model)
        (self.path / "returns").mkdir(parents=True, exist_ok=True)
        for cid in preregs[batch]["candidates"]:
            r = _returns(self._candidate(cid).signal_fn(), frame, m)
            np.save(self.path / "returns" / f"{_safe(cid)}.npy", r[max(0, n_disc - 1):])
        stats = self.family(self._validated() + list(preregs[batch]["candidates"]))
        self.log.append({"kind": "validate", "batch": batch, "n_trials": self.n_trials, "stats": stats})
        self._save(stage="validated")
        return {"batch": batch, **stats, "rows": family_rows(stats)}

    def _validated(self) -> list[str]:
        reads = {e["batch"] for e in self._entries("validate")}
        return [c for e in self._entries("prereg") if e["batch"] in reads for c in e["candidates"]]

    def family(self, ids: list[str] | None = None) -> dict[str, Any]:
        """Statistics of every validated candidate (all batches) on the validation part."""
        ids = ids or self._validated()
        if not ids:
            raise ValueError("nothing was validated yet")
        mats = [np.load(self.path / "returns" / f"{_safe(c)}.npy") for c in ids]
        n = min(len(x) for x in mats)
        ppy = float(self._entries("init")[0].get("ppy") or 252.0)
        stats = family_stats(np.vstack([x[-n:] for x in mats]), ids, ppy, spa_level=SPA_LEVEL)
        return {**stats, "n_trials_project": self.n_trials, "n_screened": len(self.screened())}

    # ---- 5. freeze and one opening of the holdout ----------------------------------------------------------------------
    def _holdout(self) -> SealedHoldout:
        return SealedHoldout(self.path / "holdout.jsonl")

    @_locked
    def freeze(self, data: pd.DataFrame | str | Path, candidate: str, *, override: bool = False) -> dict[str, Any]:
        """Freeze one validated candidate (hash of code and parameters) for the holdout. One freeze per project.

        Raises:
            ValueError: Not validated, the validation gate is closed (unless ``override``, which is written down), or already frozen.
        """
        if candidate not in self._validated():
            self._refuse("freeze", f"candidate {candidate} was not validated")
        df = self._frame(data)
        stats = self._entries("validate")[-1]["stats"]
        row = next(c for c in stats["candidates"] if c["id"] == candidate)
        gate = bool(row["stepdown_significant"] and row["beats_search_null"] and row["sharpe_annual"] > 0)
        if not gate and not override:
            self._refuse("freeze", "the validation gate is closed for this candidate (needs Romano-Wolf significance and a Sharpe above what luck delivers for this search)")
        c = self._candidate(candidate)
        entry = self._holdout().freeze(df, frozen_source(c.source, c.params), n_trials=self.n_trials, cut=self.splits.holdout_cut(df))
        out = self.log.append({"kind": "freeze", "candidate": candidate, "gate_open": gate, "override": bool(override and not gate), "holdout_hash": entry["hash"]})
        self._save(stage="frozen")
        return out

    @_locked
    def open_holdout(self, data: pd.DataFrame | str | Path, *, model: ExecutionModel | None = None) -> dict[str, Any]:
        """Run the frozen candidate on the sealed part. The first call returns evidence; any later call spoils it (D4 = 0 forever)."""
        fz = self._entries("freeze")
        if not fz:
            self._refuse("open_holdout", "nothing is frozen: freeze one validated candidate first")
        c = self._candidate(fz[0]["candidate"])
        if any(e.get("kind") == "holdout_open" for e in self._entries()):
            self.log.append({"kind": "refused", "action": "open_holdout", "reason": "the sealed holdout was already opened: a second opening spoils it for good"})
        ev = self._holdout().open(self._frame(data), c.signal_fn(), frozen_source(c.source, c.params), model=model)
        self.log.append({"kind": "holdout_open", "opens": ev["opens"], "valid": ev["valid"]})
        self._save(stage="holdout_opened")
        return ev

    def holdout_evidence(self) -> dict[str, Any]:
        return self._holdout().evidence()

    # ---- certificate ---------------------------------------------------------------------------------------------------
    @_locked
    def certify(self, data: pd.DataFrame | str | Path, **kwargs: Any) -> dict[str, Any]:
        """Certificate of the frozen candidate on all data before the holdout, with the project's ``n_trials`` and the family rows."""
        from monte_neo.verify import verify_strategy

        fz = self._entries("freeze")
        if not fz:
            raise ValueError("nothing is frozen: freeze one validated candidate first")
        df = self._frame(data)
        c = self._candidate(fz[0]["candidate"])
        rep = verify_strategy(self.splits.upto(df, "validation"), signal_fn=c.signal_fn(), source=frozen_source(c.source, c.params),
                              n_trials=self.n_trials, extra_checks=family_rows(self._entries("validate")[-1]["stats"]), **kwargs)
        (self.path / "certificate.json").write_text(json.dumps(rep, default=str), encoding="utf-8")
        self.log.append({"kind": "certify", "certificate_id": rep.get("certificate_id"), "verdict": rep.get("verdict")})
        return rep


    def certify_candidate(self, data: pd.DataFrame | str | Path | None, cid: str, **kwargs: Any) -> dict[str, Any]:
        """Certificate of one validated candidate on all data before the holdout, with the project's ``n_trials`` (stored under ``certificates/``)."""
        from monte_neo.verify import verify_strategy

        if cid not in self._validated():
            raise ValueError(f"candidate {cid} was not validated")
        with self.lock.held():
            df = self._frame(data)
            c = self._candidate(cid)
            rep = verify_strategy(self.splits.upto(df, "validation"), signal_fn=c.signal_fn(), source=frozen_source(c.source, c.params), n_trials=self.n_trials,
                                  extra_checks=family_rows(self._entries("validate")[-1]["stats"]), **kwargs)
            from monte_neo.research.manifest import atomic_write

            atomic_write(self.path / "certificates" / f"{_safe(cid)}.json", json.dumps(rep, default=str))
            self.log.append({"kind": "certify_candidate", "candidate": cid, "certificate_id": rep.get("certificate_id"), "verdict": rep.get("verdict")})
            return rep

    def certificate_of(self, cid: str) -> dict[str, Any] | None:
        f = self.path / "certificates" / f"{_safe(cid)}.json"
        if f.is_file():
            return json.loads(f.read_text(encoding="utf-8"))
        fz = self._entries("freeze")
        cert = self.path / "certificate.json"
        return json.loads(cert.read_text(encoding="utf-8")) if fz and fz[0]["candidate"] == cid and cert.is_file() else None


__all__ = ["SCHEMA", "ResearchProject", "list_sha"]
