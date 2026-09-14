"""Performance smoke for L2 Numba walk."""

from __future__ import annotations

import time

import numpy as np
import pytest

from monte_neo.oms.accel.match_l2_numba import walk_book_market
from monte_neo.oms.book import book_from_mid


@pytest.mark.performance
def test_l2_walk_throughput_smoke() -> None:
    book = book_from_mid(100.0, depth=10, size=100.0)
    bid_px, bid_sz, ask_px, ask_sz = book.to_arrays(10)
    _ = walk_book_market(1, 1.0, bid_px, bid_sz, ask_px, ask_sz, 5.0, 0.0)
    t0 = time.perf_counter()
    n = 50_000
    for _ in range(n):
        walk_book_market(1, 5.0, bid_px, bid_sz, ask_px, ask_sz, 5.0, 0.0)
    elapsed = time.perf_counter() - t0
    rate = n / elapsed if elapsed > 0 else 0.0
    assert rate > 1_000.0
