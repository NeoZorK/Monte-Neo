"""Performance smoke for Metal/Numba L2 batch walks."""

from __future__ import annotations

import time

import numpy as np
import pytest

from monte_neo.oms.accel.metal_l2 import run_l2_walk_batch
from monte_neo.oms.book import book_from_mid


@pytest.mark.performance
def test_l2_batch_auto_throughput_smoke() -> None:
    book = book_from_mid(100.0, depth=10, size=50.0)
    bid_px, bid_sz, ask_px, ask_sz = book.to_arrays(10)
    n = 4_096
    sides = np.where(np.arange(n) % 2 == 0, 1, -1).astype(np.int32)
    qtys = np.full(n, 3.0, dtype=np.float64)
    _ = run_l2_walk_batch(
        sides[:64], qtys[:64], bid_px, bid_sz, ask_px, ask_sz, device="auto"
    )
    t0 = time.perf_counter()
    out = run_l2_walk_batch(
        sides, qtys, bid_px, bid_sz, ask_px, ask_sz, commission_bps=5.0, device="auto"
    )
    elapsed = time.perf_counter() - t0
    rate = n / elapsed if elapsed > 0 else 0.0
    assert out["ok"] is True
    assert np.all(np.isfinite(out["filled"]))
    assert rate > 500.0
