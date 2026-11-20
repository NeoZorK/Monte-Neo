"""Forward record: hash chain and freeze guard (no network)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "strategy_lab"))
import forward_record as fr  # noqa: E402


def _row(prev, day):
    body = {"day": day, "candidates": {}, "prev_hash": prev}
    import hashlib
    return {**body, "hash": hashlib.sha256((prev + fr.canon(body)).encode()).hexdigest()}


def test_chain_detects_tampering():
    a = _row("0" * 64, "2026-11-10")
    b = _row(a["hash"], "2026-11-11")
    assert fr.verify_chain([a, b])
    b2 = {**b, "day": "2026-11-12"}
    assert not fr.verify_chain([a, b2])
    assert not fr.verify_chain([b, a])


def test_frozen_spec_stable_and_guarded(tmp_path, monkeypatch):
    spec = fr.frozen_spec()
    assert fr.frozen_spec() == spec and spec["start"] == "2026-11-10"
    monkeypatch.setattr(fr, "FWD", tmp_path)
    with pytest.raises(SystemExit):
        fr.check_frozen()  # not frozen yet: refuses
    (tmp_path / "frozen.json").write_text(__import__("json").dumps({**spec, "code_files": {"x": "bad"}}))
    with pytest.raises(SystemExit):
        fr.check_frozen()  # changed hashes: refuses
