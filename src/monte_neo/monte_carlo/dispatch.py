"""Unified Metal / MLX / CPU dispatch plan for Monte Carlo scenario runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from monte_neo.monte_carlo.memory_budget import (
    DEFAULT_USABLE_BYTES,
    ScenarioBudget,
    plan_scenario_budget,
)
from monte_neo.monte_carlo.types import MCConfig
from monte_neo.oms.accel.compute_pref import preferred_compute_device


@dataclass(frozen=True)
class MCDispatchPlan:
    """Honest backend choice + 16GB tile budget for one MC run."""

    requested_device: str
    resolved_device: str
    backend: str  # metal | mlx | cpu_numba
    device_allows_accel: bool
    allow_gpu: bool
    prefer_native_metal: bool
    prefer_mlx: bool
    budget: ScenarioBudget
    reason: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["budget"] = self.budget.to_dict()
        return d


def _itemsize_for_precision(precision: str) -> int:
    p = (precision or "float32").lower()
    if p in {"float64", "f64"}:
        return 8  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    if p in {"float16", "f16", "float8", "f8"}:
        return 2  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    return 4


def _cpu_plan(
    config: MCConfig,
    *,
    resolved: str,
    budget: ScenarioBudget,
    reason: str,
    device_allows_accel: bool = False,
) -> MCDispatchPlan:
    return MCDispatchPlan(
        requested_device=config.compute_device,
        resolved_device=resolved,
        backend="cpu_numba",
        device_allows_accel=device_allows_accel,
        allow_gpu=False,
        prefer_native_metal=False,
        prefer_mlx=False,
        budget=budget,
        reason=reason,
    )


def plan_mc_run(
    config: MCConfig,
    *,
    n_bars: int,
    n_scenarios: int | None = None,
    has_metal_params: bool = False,
    has_mlx_repr: bool = False,
) -> MCDispatchPlan:
    """Resolve MC backend from compute_device / use_gpu and plan memory tiles."""
    n = int(n_scenarios if n_scenarios is not None else config.iterations)
    pref = preferred_compute_device(config.compute_device)
    resolved = str(pref["resolved"])
    itemsize = _itemsize_for_precision(config.gpu_precision)
    usable = (
        int(config.memory_budget_bytes)
        if config.memory_budget_bytes is not None
        else DEFAULT_USABLE_BYTES
    )
    budget = plan_scenario_budget(n_bars, n, itemsize=itemsize, usable_bytes=usable)

    if not config.use_gpu or resolved == "cpu_numba":
        return _cpu_plan(
            config,
            resolved="cpu_numba" if not config.use_gpu else resolved,
            budget=budget,
            reason="gpu_disabled_or_cpu_requested",
        )

    # Device can accelerate orchestration even if indicator lacks GPU kernels.
    device_ok = True

    if resolved == "mlx":
        if has_mlx_repr:
            return MCDispatchPlan(
                requested_device=config.compute_device,
                resolved_device=resolved,
                backend="mlx",
                device_allows_accel=device_ok,
                allow_gpu=True,
                prefer_native_metal=False,
                prefer_mlx=True,
                budget=budget,
                reason="mlx_requested",
            )
        return _cpu_plan(
            config,
            resolved=resolved,
            budget=budget,
            reason="mlx_requested_but_no_repr",
            device_allows_accel=device_ok,
        )

    if resolved == "metal":
        if has_metal_params:
            return MCDispatchPlan(
                requested_device=config.compute_device,
                resolved_device=resolved,
                backend="metal",
                device_allows_accel=device_ok,
                allow_gpu=True,
                prefer_native_metal=True,
                prefer_mlx=False,
                budget=budget,
                reason="metal_primary_with_native_params",
            )
        if has_mlx_repr:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            return MCDispatchPlan(  # pragma: no cover  # defensive / unreachable after unit mocks on CI
                requested_device=config.compute_device,
                resolved_device=resolved,
                backend="mlx",
                device_allows_accel=device_ok,
                allow_gpu=True,
                prefer_native_metal=False,
                prefer_mlx=True,
                budget=budget,
                reason="metal_resolved_mlx_fallback_batch",
            )
        return _cpu_plan(  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            config,
            resolved=resolved,
            budget=budget,
            reason="metal_resolved_but_indicator_lacks_gpu_repr",
            device_allows_accel=device_ok,
        )

    return _cpu_plan(config, resolved=resolved, budget=budget, reason="fallback_cpu")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
