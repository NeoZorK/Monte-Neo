"""Shared ledger: concurrent writers, old-format entries, lock timeout."""

from __future__ import annotations

import json
import multiprocessing as mp
from pathlib import Path

import pytest

from monte_neo.verify.filelock import LockTimeoutError, file_lock
from monte_neo.verify.ledger import GENESIS, Ledger


def _worker(path: str, tag: str, n: int) -> None:
    ledger = Ledger(path)
    for i in range(n):
        ledger.record(variant=f"{tag}{i}", data_id="d", sharpe=1.0, verdict="pass", certificate_id=f"{tag}{i}")


def test_two_processes_write_one_intact_chain(tmp_path: Path) -> None:
    path = tmp_path / "shared" / "ledger.jsonl"
    ctx = mp.get_context("spawn")
    procs = [ctx.Process(target=_worker, args=(str(path), tag, 50)) for tag in ("a", "b")]
    for p in procs:
        p.start()
    for p in procs:
        p.join(120)
        assert p.exitcode == 0
    ledger = Ledger(path)
    assert ledger.check() == {"ok": True, "entries": 100, "problem": None}
    assert len(ledger.variants("d")) == 100


def test_entries_carry_who_and_host(tmp_path: Path) -> None:
    entry = Ledger(tmp_path / "l.jsonl").record(variant="v", data_id="d", sharpe=0.5, verdict="pass", certificate_id="c", who="alice")
    assert entry["who"] == "alice"
    assert entry["host"]


def test_old_format_entries_still_verify(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    body = {"seq": 1, "prev": GENESIS, "at": "2025-01-01T00:00:00.000000+00:00", "variant": "v0", "data": "d",
            "sharpe": 1.0, "verdict": "pass", "certificate": "c0"}
    path.write_text(json.dumps({**body, "hash": Ledger._hash(GENESIS, body)}, sort_keys=True) + "\n", encoding="utf-8")
    ledger = Ledger(path)
    assert ledger.check()["ok"]
    ledger.record(variant="v1", data_id="d", sharpe=1.0, verdict="pass", certificate_id="c1")
    assert ledger.check() == {"ok": True, "entries": 2, "problem": None}


def test_lock_timeout_is_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    lock = path.with_name(path.name + ".lock")
    with file_lock(lock, 1.0):
        # flock is per open file description, so a second open in this process conflicts too
        with pytest.raises(LockTimeoutError, match="another process is writing"):
            Ledger(path).record(variant="v", data_id="d", sharpe=1.0, verdict="pass", certificate_id="c", lock_timeout=0.2)
