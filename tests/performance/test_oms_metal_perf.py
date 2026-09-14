"""Performance smoke for Metal/Numba OMS batch dispatch."""

from __future__ import annotations

import time

import numpy as np
import pytest

from monte_neo.oms.accel.metal_dispatch import run_batch_terminal


@pytest.mark.performance
def test_batch_terminal_auto_throughput_smoke() -> None:
    n = 5_000
    open_ = np.linspace(100.0, 120.0, n)
    close = open_.copy()
    sig = np.zeros((16, n), dtype=np.int64)
    sig[:, 100:4000] = 1
    # warmup
    _ = run_batch_terminal(open_[:500], close[:500], sig[:1, :500], device="auto")
    t0 = time.perf_counter()
    out = run_batch_terminal(open_, close, sig, device="auto")
    elapsed = time.perf_counter() - t0
    cps = 16 / elapsed if elapsed > 0 else 0.0
    assert out["ok"] is True
    assert np.all(np.isfinite(out["returns"]))
    assert cps > 1.0
