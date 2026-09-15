"""No-hang Metal/MLX size gates → transparent cpu_numba fallback."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from monte_neo.backtest import (
    ExecutionModel,
    decide_research_accelerator,
    export_batch,
    export_sma_sweep,
    frame_to_ohlc,
    plan_research_bytes,
    run_bar_backtest_batch,
    sma_signal,
    synthetic_ohlcv,
)
from monte_neo.backtest.memory_plan import (
    estimate_metal_shared_bytes,
    metal_max_bars,
    metal_shared_bytes_budget,
)


def test_plan_includes_metal_gate_fields() -> None:
    plan = plan_research_bytes(n_bars=1_000_000, n_combos=16)
    assert plan["metal_shared_bytes_est"] == estimate_metal_shared_bytes(
        n_bars=1_000_000, n_combos=16
    )
    assert plan["fits_metal_shared"] is True
    assert plan["bytes_budget"] <= 8 * (1024**3)


def test_ten_million_exceeds_metal_max_bars() -> None:
    plan = plan_research_bytes(n_bars=10_000_000, n_combos=16)
    assert plan["n_bars"] > metal_max_bars()
    assert plan["fits_metal_shared"] is False
    with patch(
        "monte_neo.oms.accel.device.resolve_device", return_value="metal"
    ):
        decision = decide_research_accelerator(
            n_bars=10_000_000, n_combos=16, device="metal"
        )
    assert decision["use_metal"] is False
    assert decision["fallback_reason"] == "metal_max_bars_exceeded"


def test_shared_budget_blocks_or_tiles_dense_metal_grid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Tiny Metal shared budget: even modest grids must refuse or tile hard.
    monkeypatch.setenv("MONTE_NEO_METAL_SHARED_BYTES_BUDGET", str(64 * 1024))  # 64 KiB
    n_bars = 50_000
    n_combos = 64
    with patch("monte_neo.oms.accel.device.resolve_device", return_value="metal"):
        decision = decide_research_accelerator(
            n_bars=n_bars, n_combos=n_combos, device="metal"
        )
    # Fixed OHLC+session alone may exceed 64KiB → refuse; else tile down.
    if decision["use_metal"]:
        assert decision["metal_tile_combos"] < n_combos
        assert decision["plan"]["fits_metal_shared"] is True
    else:
        assert decision["fallback_reason"] in {
            "metal_shared_bytes_budget_exceeded",
            "research_bytes_budget_exceeded",
            "metal_max_bars_exceeded",
        }


def test_env_shared_budget_forces_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONTE_NEO_METAL_SHARED_BYTES_BUDGET", "1024")  # 1 KiB impossible
    with patch("monte_neo.oms.accel.device.resolve_device", return_value="metal"):
        decision = decide_research_accelerator(
            n_bars=100_000, n_combos=8, device="metal"
        )
    assert decision["use_metal"] is False
    assert decision["fallback_reason"] == "metal_shared_bytes_budget_exceeded"


def test_small_case_allows_metal_when_resolved() -> None:
    with patch("monte_neo.oms.accel.device.resolve_device", return_value="metal"):
        decision = decide_research_accelerator(
            n_bars=50_000, n_combos=16, device="auto"
        )
    assert decision["use_metal"] is True
    assert decision["fallback_reason"] is None


def test_batch_oversized_falls_back_without_calling_metal_engine() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(800, seed=3))
    # Pretend series is 10M bars for the gate only by patching decide.
    sigs = np.stack(
        [sma_signal(ohlc["close"], 5, 30), sma_signal(ohlc["close"], 8, 40)]
    )
    model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=40)

    blocked = {
        "want_device": "metal",
        "use_metal": False,
        "use_mlx": False,
        "fallback_reason": "metal_max_bars_exceeded",
        "plan": plan_research_bytes(n_bars=10_000_000, n_combos=2),
        "metal_tile_combos": 1,
    }
    with patch(
        "monte_neo.backtest.batch.decide_research_accelerator", return_value=blocked
    ), patch(
        "monte_neo.backtest.batch.try_metal_batch_returns"
    ) as try_metal, patch(
        "monte_neo.backtest.batch.metal_economics_eligible", return_value=True
    ):
        out = run_bar_backtest_batch(
            ohlc["open"],
            ohlc["high"],
            ohlc["low"],
            ohlc["close"],
            sigs,
            model=model,
            device="auto",
        )
        try_metal.assert_not_called()
    assert out["device"] == "cpu_numba"
    assert out["fallback_reason"] == "metal_max_bars_exceeded"
    assert out["ok"] is True
    assert out["combos"] == 2


def test_export_sma_sweep_propagates_fallback_reason() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(500, seed=11))
    model = ExecutionModel(side_mode="long_flat", commission_bps=5.0, warmup_bars=40)
    blocked = {
        "want_device": "metal",
        "use_metal": False,
        "use_mlx": False,
        "fallback_reason": "metal_max_bars_exceeded",
        "plan": plan_research_bytes(n_bars=10_000_000, n_combos=8),
        "metal_tile_combos": 1,
    }
    with patch(
        "monte_neo.backtest.sweep.decide_research_accelerator", return_value=blocked
    ), patch(
        "monte_neo.backtest.batch.decide_research_accelerator", return_value=blocked
    ), patch(
        "monte_neo.backtest.batch.metal_economics_eligible", return_value=True
    ):
        out = export_sma_sweep(
            ohlc["open"],
            ohlc["high"],
            ohlc["low"],
            ohlc["close"],
            combos=8,
            model=model,
            device="auto",
        )
    assert out["device"] == "cpu_numba"
    assert out["signal_device"] == "cpu_numba"
    assert out.get("fallback_reason") == "metal_max_bars_exceeded"


def test_export_batch_small_cpu_still_ok() -> None:
    ohlc = frame_to_ohlc(synthetic_ohlcv(300, seed=2))
    sigs = np.stack([sma_signal(ohlc["close"], 5, 30), sma_signal(ohlc["close"], 8, 40)])
    model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=40)
    out = export_batch(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        sigs,
        model=model,
        device="cpu_numba",
    )
    assert out["device"] == "cpu_numba"
    assert "fallback_reason" not in out
