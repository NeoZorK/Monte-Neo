"""Integration tests for OMS paper lane."""

from __future__ import annotations

import numpy as np

from monte_neo.backtest import frame_to_ohlc, sma_signal, synthetic_ohlcv
from monte_neo.oms import SignalStrategy, run_oms_bar_backtest


def test_oms_on_synthetic_sma() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(2_000, seed=17))
    sig = sma_signal(ohlc["close"], 10, 40)
    out = run_oms_bar_backtest(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        SignalStrategy(sig, size_fraction=0.25),
        commission_bps=5.0,
        slippage_bps=5.0,
        warmup_bars=40,
        device="cpu_numba",
    )
    assert out["ok"] is True
    assert out["equity"].shape[0] == 2_000
    assert out["blotter"]["n_orders"] >= 0
    assert np.isfinite(out["final_cash"])
