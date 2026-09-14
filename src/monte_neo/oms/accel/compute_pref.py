"""Monte Carlo / OMS shared device preference helper."""

from __future__ import annotations

from typing import Any

from monte_neo.oms.accel.device import (
    metal_available,
    mlx_available,
    resolve_device,
    work_checklist_accel,
)


def preferred_compute_device(requested: str = "auto") -> dict[str, Any]:
    """Resolve compute device for MC + bulk OMS with an honest checklist."""
    used = resolve_device(requested)
    return {
        "requested": requested,
        "resolved": used,
        "checklist": work_checklist_accel(used),
        "metal_available": metal_available(),
        "mlx_available": mlx_available(),
        "host_hint": "Prefer Metal on Apple Silicon 16GB-class hosts for bulk grids",
    }
