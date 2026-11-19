"""The sealed holdout opens once; a second open spoils D4 for good, and the file says why."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from monte_neo.arl_depth import MET, UNMET, Evidence, _path, depth_for_level
from monte_neo.backtest import synthetic_ohlcv
from monte_neo.readiness import readiness
from monte_neo.verify.sealed_holdout import SealedHoldout

DF = synthetic_ohlcv(1200, seed=2)
SRC = "import numpy as np\n\n\ndef signal(df):\n    return np.where(np.arange(len(df)) % 40 < 20, 1, 0)\n"


def signal(df: pd.DataFrame) -> np.ndarray:
    return np.where(np.arange(len(df)) % 40 < 20, 1, 0)


def _sealed(tmp_path) -> SealedHoldout:
    h = SealedHoldout(tmp_path / "h.jsonl")
    h.freeze(DF, SRC, fraction=0.25, n_trials=3)
    return h


def test_freeze_open_once_gives_valid_evidence(tmp_path) -> None:
    h = _sealed(tmp_path)
    before = h.evidence()
    assert before["valid"] is False and "not opened yet" in before["reason"]
    ev = h.open(DF, signal, SRC)
    assert ev["valid"] is True and ev["opens"] == 1 and ev["reason"] is None and ev["certificate_id"]
    assert any(c["id"] == "net_profitability" for c in ev["checks"])
    kinds = [e["kind"] for e in h.log.entries()]
    assert kinds == ["freeze", "open"]
    assert h.log.entries()[0]["n_trials"] == 3


def test_second_open_spoils_the_holdout_permanently(tmp_path) -> None:
    h = _sealed(tmp_path)
    h.open(DF, signal, SRC)
    again = h.open(DF, signal, SRC)
    assert again["valid"] is False and "more than once" in again["reason"]
    assert h.log.entries()[-1]["kind"] == "reopen" and "more than once" in h.log.entries()[-1]["reason"]
    third = SealedHoldout(tmp_path / "h.jsonl").evidence()  # a fresh object reads the same ledger: no way back
    assert third["valid"] is False
    rep = readiness(None, holdout=third)
    for lv in rep["levels"]:
        d4 = next(c for c in lv["depth_criteria"] if c["id"] == "D4")
        assert d4["state"] == UNMET and "permanently" in d4["why"]


def test_open_requires_the_frozen_data_and_strategy(tmp_path) -> None:
    h = _sealed(tmp_path)
    with pytest.raises(ValueError, match="strategy changed"):
        h.open(DF, signal, SRC.replace("% 40", "% 41"))  # a real change; comments do not count
    with pytest.raises(ValueError, match="not the data"):
        h.open(synthetic_ohlcv(1200, seed=9), signal, SRC)
    assert h.evidence()["opens"] == 0  # refused attempts do not open it


def test_freeze_validation_and_single_freeze(tmp_path) -> None:
    h = SealedHoldout(tmp_path / "x.jsonl")
    for kw in ({"fraction": 0.01}, {"fraction": 0.9}, {"n_trials": 0}):
        with pytest.raises(ValueError, match="fraction must be"):
            h.freeze(DF, SRC, **kw)
    h.freeze(DF, SRC)
    with pytest.raises(ValueError, match="already holds a freeze"):
        h.freeze(DF, SRC)


def test_open_before_freeze_and_tampering(tmp_path) -> None:
    h = SealedHoldout(tmp_path / "empty.jsonl")
    with pytest.raises(ValueError, match="never frozen"):
        h.open(DF, signal, SRC)
    assert h.evidence()["valid"] is False and "never frozen" in h.evidence()["reason"]
    s = _sealed(tmp_path)
    s.open(DF, signal, SRC)
    path = tmp_path / "h.jsonl"
    lines = path.read_text().splitlines()
    path.write_text("\n".join([json.dumps({**json.loads(lines[1]), "verdict": "PASS"}), lines[0]][::-1]) + "\n")  # edited and reordered
    ev = SealedHoldout(path).evidence()
    assert ev["valid"] is False and "changed" in ev["reason"]
    with pytest.raises(ValueError, match="changed"):
        SealedHoldout(path).open(DF, signal, SRC)


def test_evidence_feeds_d4_through_readiness(tmp_path) -> None:
    h = _sealed(tmp_path)
    ev = h.open(DF, signal, SRC)
    e = Evidence({}, metrics={}, holdout=ev, n_trials=1)
    got = depth_for_level(3, e)["criteria"][3]
    assert got["id"] == "D4" and got["state"] in (MET, UNMET)  # decided by the holdout's own net_profitability row
    assert got["state"] == (MET if next(c for c in ev["checks"] if c["id"] == "net_profitability")["status"] == "pass" else UNMET)


def test_timestamps_missing_use_positions(tmp_path) -> None:
    plain = DF.drop(columns=[c for c in DF.columns if c == "timestamp"]) if "timestamp" in DF.columns else DF
    h = SealedHoldout(tmp_path / "p.jsonl")
    h.freeze(plain, SRC)
    assert h.open(plain, signal, SRC)["valid"] is True


def test_path_helper_stops_on_scalars() -> None:
    assert _path({"a": "text"}, "a.b") is None and _path({"a": [1, 2]}, "a.5") is None and _path({"a": [1, 2]}, "a.1") == 2
