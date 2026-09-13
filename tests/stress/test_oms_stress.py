"""Stress tests for OMS Numba batch path."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.backtest import frame_to_ohlc, sma_signal, synthetic_ohlcv
from monte_neo.oms.accel.match_numba import batch_terminal_long_flat


@pytest.mark.stress
def test_oms_numba_batch_50k_bars() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(50_000, seed=3))
    rows = [
        sma_signal(ohlc["close"], f, s) for f, s in ((5, 30), (8, 35), (10, 40), (12, 48))
    ]
    sig = np.vstack(rows)
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
    assert rets.shape[0] == 4
    assert np.all(np.isfinite(rets))
