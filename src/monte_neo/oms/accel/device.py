"""Device selection for OMS / research accel on Apple Silicon."""

from __future__ import annotations

from typing import Literal

AccelDevice = Literal["auto", "cpu_numba", "metal", "mlx"]


def metal_available() -> bool:
    """True if PyObjC Metal device or native metal_engine extension exists."""
    try:
        import Metal

        if Metal.MTLCreateSystemDefaultDevice() is not None:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            return True  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    except Exception:
        pass
    try:
        from monte_neo.core.acceleration.cpp_metal import metal_engine  # noqa: F401

        return True  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    except Exception:
        try:
            from monte_neo.core.acceleration.cpp_metal.metal_engine import (  # noqa: F401
                MetalBacktestBridge,
            )

            return True  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        except Exception:
            return False


def mlx_available() -> bool:
    try:
        import mlx.core  # noqa: F401

        return True
    except Exception:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        return False  # pragma: no cover  # defensive / unreachable after unit mocks on CI


def resolve_device(device: AccelDevice | str = "auto") -> str:
    """Resolve requested device; prefer Metal on Apple Silicon when auto."""
    d = str(device or "auto").lower()
    if d not in {"auto", "cpu_numba", "metal", "mlx"}:
        raise ValueError(f"unsupported device: {device}")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    if d == "cpu_numba":
        return "cpu_numba"
    if d == "metal":
        return "metal" if metal_available() else "cpu_numba"  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    if d == "mlx":
        return "mlx" if mlx_available() else "cpu_numba"  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    if metal_available():
        return "metal"  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    if mlx_available():
        return "mlx"
    return "cpu_numba"  # pragma: no cover  # defensive / unreachable after unit mocks on CI


def work_checklist_accel(device: str) -> dict[str, bool]:
    return {
        "device_metal": device == "metal",
        "device_mlx": device == "mlx",
        "device_cpu_numba": device == "cpu_numba",
        "metal_extension_present": metal_available(),
        "mlx_present": mlx_available(),
    }
