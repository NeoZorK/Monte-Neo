"""OMS accel package: device select + future Metal kernels."""

from __future__ import annotations

from monte_neo.oms.accel.device import (
    AccelDevice,
    metal_available,
    mlx_available,
    resolve_device,
    work_checklist_accel,
)

__all__ = [
    "AccelDevice",
    "metal_available",
    "mlx_available",
    "resolve_device",
    "work_checklist_accel",
]
