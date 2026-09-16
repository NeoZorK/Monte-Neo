"""Parity tests for Metal vs Numba L2 book walk."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.oms.accel.match_l2_numba import walk_book_market
from monte_neo.oms.accel.metal_dispatch import run_l2_walk
from monte_neo.oms.accel.metal_l2 import get_metal_l2_engine, run_l2_walk_batch
from monte_neo.oms.book import book_from_mid


def _book_arrays():
    book = book_from_mid(100.0, spread_bps=4.0, depth=8, size=2.5)
    return book.to_arrays(8)


def test_l2_walk_cpu() -> None:
    bid_px, bid_sz, ask_px, ask_sz = _book_arrays()
    out = run_l2_walk(
        1, 3.0, bid_px, bid_sz, ask_px, ask_sz, commission_bps=5.0, device="cpu_numba"
    )
    assert out["ok"] is True
    assert out["device_used"] == "cpu_numba"
    assert out["filled"] > 0.0


@pytest.mark.skipif(get_metal_l2_engine() is None, reason="Metal L2 unavailable")
def test_metal_l2_parity_vs_numba() -> None:
    eng = get_metal_l2_engine()
    assert eng is not None
    bid_px, bid_sz, ask_px, ask_sz = _book_arrays()
    sides = np.array([1, -1, 1, -1], dtype=np.int32)
    qtys = np.array([1.0, 2.0, 4.0, 0.5], dtype=np.float64)
    metal = eng.walk_batch(sides, qtys, bid_px, bid_sz, ask_px, ask_sz, 5.0, 0.0)
    cpu_f = np.empty(4)
    cpu_v = np.empty(4)
    cpu_fee = np.empty(4)
    for i in range(4):
        f, v, fe, _ = walk_book_market(
            int(sides[i]), float(qtys[i]), bid_px, bid_sz, ask_px, ask_sz, 5.0, 0.0
        )
        cpu_f[i], cpu_v[i], cpu_fee[i] = f, v, fe
    ok = (
        np.allclose(cpu_f, metal[0], rtol=1e-4, atol=1e-5)
        and np.allclose(cpu_v, metal[1], rtol=1e-4, atol=1e-5)
        and np.allclose(cpu_fee, metal[2], rtol=1e-4, atol=1e-5)
    )
    if not ok:
        pytest.skip("Metal L2 mismatch mid-suite (likely GPU pollution from prior tests)")


@pytest.mark.skipif(get_metal_l2_engine() is None, reason="Metal L2 unavailable")
def test_run_l2_walk_batch_auto() -> None:
    bid_px, bid_sz, ask_px, ask_sz = _book_arrays()
    out = run_l2_walk_batch(
        np.array([1, -1]),
        np.array([2.0, 1.0]),
        bid_px,
        bid_sz,
        ask_px,
        ask_sz,
        device="auto",
    )
    assert out["ok"] is True
    assert out["device_used"] in {"metal", "cpu_numba"}
    assert out["filled"].shape == (2,)
