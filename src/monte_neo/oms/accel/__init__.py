"""OMS accel package: device select + Metal/Numba dispatch."""

from __future__ import annotations

from monte_neo.oms.accel.compute_pref import preferred_compute_device
from monte_neo.oms.accel.device import (
    AccelDevice,
    metal_available,
    mlx_available,
    resolve_device,
    work_checklist_accel,
)
from monte_neo.oms.accel.metal_dispatch import run_batch_terminal, run_l2_walk
from monte_neo.oms.accel.metal_l2 import run_l2_walk_batch

__all__ = [
    "AccelDevice",
    "metal_available",
    "mlx_available",
    "preferred_compute_device",
    "resolve_device",
    "run_batch_terminal",
    "run_l2_walk",
    "run_l2_walk_batch",
    "work_checklist_accel",
]
