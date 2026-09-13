"""Performance smoke for fee-aware SMA sweep (not a ClaimBound gate)."""

from __future__ import annotations

import pytest

from monte_neo.backtest import ExecutionModel, frame_to_ohlc, run_sma_sweep, synthetic_ohlcv


@pytest.mark.performance
def test_fee_aware_sweep_throughput_smoke() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(n_bars=20_000, seed=42))
    model = ExecutionModel(
        commission_bps=5.0,
        slippage_bps=5.0,
        size_fraction=0.25,
        warmup_bars=60,
    )
    out = run_sma_sweep(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        combos=64,
        model=model,
    )
    assert out["ok"] is True
    # Generous floor: ensures the path is usable; not a public claim.
    assert out["combos_per_s"] > 10.0
