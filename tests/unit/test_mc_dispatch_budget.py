"""Unit tests for MC memory budget + Metal/MLX dispatch unify."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from monte_neo.monte_carlo.dispatch import plan_mc_run
from monte_neo.monte_carlo.engine import MonteCarloEngine
from monte_neo.monte_carlo.memory_budget import (
    DEFAULT_USABLE_BYTES,
    iter_scenario_tiles,
    plan_scenario_budget,
)
from monte_neo.monte_carlo.types import MCConfig


def test_plan_scenario_budget_tiles_under_usable() -> None:
    bud = plan_scenario_budget(50_000, 100_000, itemsize=4)
    assert bud.bytes_peak_est <= DEFAULT_USABLE_BYTES
    assert bud.tile_scenarios >= 1
    assert bud.bytes_per_scenario > 0
    assert not bud.fits_in_one_tile or bud.n_scenarios <= bud.tile_scenarios


def test_plan_scenario_budget_small_fits() -> None:
    bud = plan_scenario_budget(100, 10, itemsize=4, usable_bytes=64 * 1024 * 1024)
    assert bud.fits_in_one_tile
    assert bud.tile_scenarios == 10


def test_iter_scenario_tiles_covers_all() -> None:
    ranges = iter_scenario_tiles(25, 10)
    assert ranges == [(0, 10), (10, 20), (20, 25)]
    assert ranges[-1][1] == 25


def test_plan_mc_run_cpu_when_gpu_disabled() -> None:
    cfg = MCConfig(use_gpu=False, compute_device="auto", iterations=200)
    plan = plan_mc_run(cfg, n_bars=1000, has_metal_params=True, has_mlx_repr=True)
    assert plan.backend == "cpu_numba"
    assert plan.allow_gpu is False


def test_plan_mc_run_cpu_device() -> None:
    cfg = MCConfig(use_gpu=True, compute_device="cpu_numba", iterations=200)
    plan = plan_mc_run(cfg, n_bars=1000, has_metal_params=True, has_mlx_repr=True)
    assert plan.backend == "cpu_numba"
    assert plan.allow_gpu is False


def test_plan_mc_run_metal_when_params() -> None:
    cfg = MCConfig(use_gpu=True, compute_device="metal", iterations=500)
    with patch(
        "monte_neo.monte_carlo.dispatch.preferred_compute_device",
        return_value={"resolved": "metal"},
    ):
        plan = plan_mc_run(cfg, n_bars=2000, has_metal_params=True, has_mlx_repr=True)
    assert plan.backend == "metal"
    assert plan.prefer_native_metal is True
    assert plan.allow_gpu is True


def test_plan_mc_run_mlx_when_requested() -> None:
    cfg = MCConfig(use_gpu=True, compute_device="mlx", iterations=500)
    with patch(
        "monte_neo.monte_carlo.dispatch.preferred_compute_device",
        return_value={"resolved": "mlx"},
    ):
        plan = plan_mc_run(cfg, n_bars=2000, has_metal_params=True, has_mlx_repr=True)
    assert plan.backend == "mlx"
    assert plan.prefer_mlx is True


def test_plan_mc_run_respects_custom_budget() -> None:
    cfg = MCConfig(
        use_gpu=True,
        compute_device="cpu_numba",
        iterations=10_000,
        memory_budget_bytes=8 * 1024 * 1024,
    )
    plan = plan_mc_run(cfg, n_bars=50_000)
    assert plan.budget.usable_bytes == 8 * 1024 * 1024
    assert plan.budget.bytes_peak_est <= plan.budget.usable_bytes


def test_engine_skips_gpu_when_cpu_device() -> None:
    cfg = MCConfig(
        iterations=50,
        n_workers=1,
        use_gpu=True,
        compute_device="cpu_numba",
        use_shuffling=True,
        use_noise=False,
        use_sensitivity=False,
        use_walk_forward=False,
        use_block_bootstrap=False,
    )
    engine = MonteCarloEngine(config=cfg)
    data = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100],
        }
    )
    indicator = MagicMock()
    indicator.to_mlx_representation.return_value = {"ok": True}
    indicator.get_metal_params.return_value = [1.0]
    engine.gpu_engine.backtest_scenarios = MagicMock(
        side_effect=AssertionError("GPU should not run")
    )
    engine.scenario_builder.generate = MagicMock(return_value=[data] * 12)
    engine._run_cpu_parallel = MagicMock(
        return_value={"passed_count": 0, "all_results": [{"scenario_idx": 0, "passed": False, "metrics": {}}] * 12}
    )
    res = engine.run(data, indicator, MagicMock(), {"total_return": 0.0})
    engine.gpu_engine.backtest_scenarios.assert_not_called()
    assert res.device_used == "cpu_numba"
    assert res.accel_plan.get("backend") == "cpu_numba"
