"""Memory plan + export equity/journal depth."""

from __future__ import annotations

import numpy as np

from monte_neo.backtest import (
    ExecutionModel,
    export_batch,
    export_single,
    frame_to_ohlc,
    plan_research_bytes,
    sma_signal,
    synthetic_ohlcv,
)


def test_plan_research_bytes_basic() -> None:
    plan = plan_research_bytes(n_bars=1_000_000, n_combos=256)
    assert plan["bytes_peak_est"] > 0
    assert plan["host_class"] == "apple_silicon_16gb"
    assert "tile_combos_hint" in plan


def test_export_single_equity_stride_and_journal() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(400, seed=9))
    sig = sma_signal(ohlc["close"], 10, 40)
    model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=40)
    out = export_single(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model,
        include_equity=True, equity_stride=10, include_journal=True, memory_plan=True,
    )
    assert out["ok"]
    assert out["equity_stride"] == 10
    assert out["equity"].ndim == 1
    assert len(out["equity"]) <= 40
    assert isinstance(out["journal"], list)
    assert out["memory"]["n_bars"] == 400


def test_export_batch_includes_memory() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(300, seed=2))
    sigs = np.stack([sma_signal(ohlc["close"], 5, 30), sma_signal(ohlc["close"], 8, 40)])
    model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=40)
    out = export_batch(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sigs,
        model=model, device="cpu_numba",
    )
    assert out["memory"]["n_combos"] == 2
