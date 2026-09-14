"""Performance smoke for OMS Numba batch (not a public claim)."""

from __future__ import annotations

import time

import numpy as np
import pytest

from monte_neo.backtest import frame_to_ohlc, sma_signal, synthetic_ohlcv
from monte_neo.oms.accel.match_numba import batch_terminal_long_flat


@pytest.mark.performance
def test_oms_numba_batch_throughput_smoke() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(20_000, seed=9))
    pairs = [(f, s) for f in range(5, 13) for s in range(30, 46) if f < s][:32]
    sig = np.vstack([sma_signal(ohlc["close"], f, s) for f, s in pairs])
    _ = batch_terminal_long_flat(
        ohlc["open"][:500],
        ohlc["close"][:500],
        sig[:1, :500],
        5.0,
        5.0,
        100_000.0,
        0.25,
        10,
    )
    t0 = time.perf_counter()
    rets = batch_terminal_long_flat(
        ohlc["open"],
        ohlc["close"],
        sig,
        5.0,
        5.0,
        100_000.0,
        0.25,
        60,
    )
    elapsed = time.perf_counter() - t0
    cps = len(pairs) / elapsed if elapsed > 0 else 0.0
    assert np.all(np.isfinite(rets))
    assert cps > 5.0
