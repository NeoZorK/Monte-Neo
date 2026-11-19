"""Proof that extending the signal grammar did not change the pre-registered batch 1 strategies.

    check_batch1_invariance.py --record   write SHA-256 of signals.score() output of every batch1 spec (run BEFORE changing signals.py)
    check_batch1_invariance.py            recompute and compare byte for byte; exit 1 on any difference

The hash covers the index, the columns and the raw float64 bytes of the discovery-panel score frame. Not investment advice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys

import numpy as np
import pandas as pd
from screen import BATCHES, panel_disc, signals

BASE = BATCHES / "batch1_score_hashes.json"


def digest(sc: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(json.dumps([str(c) for c in sc.columns]).encode())
    h.update(np.ascontiguousarray(sc.index.values.astype("datetime64[ns]")).tobytes())
    h.update(np.ascontiguousarray(sc.to_numpy(dtype="float64")).tobytes())
    return h.hexdigest()


def compute() -> dict[str, str]:
    close, volume = panel_disc()
    batch = json.loads((BATCHES / "batch1.json").read_text())
    return {c["id"]: digest(signals.score(close, volume, c["spec"])) for c in batch["candidates"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    a = ap.parse_args()
    now = compute()
    if a.record:
        BASE.write_text(json.dumps(now, indent=1))
        print(f"recorded {len(now)} hashes")
        return 0
    old = json.loads(BASE.read_text())
    bad = [k for k in old if now.get(k) != old[k]]
    for k, v in now.items():
        print(k, v[:16], "OK" if k not in bad else "DIFFERS")
    print("INVARIANT: all identical" if not bad and set(old) == set(now) else f"BROKEN: {bad}")
    return 0 if not bad and set(old) == set(now) else 1


if __name__ == "__main__":
    sys.exit(main())
