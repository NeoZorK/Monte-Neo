"""M1 Pro 16GB-class research memory planning + accelerator no-hang gates."""

from __future__ import annotations

import os
from typing import Any

# Soft host budget for research working sets on a 16GB Apple Silicon class machine.
# Leave headroom for OS + Python + copies; override via MONTE_NEO_RESEARCH_BYTES_BUDGET.
_DEFAULT_RESEARCH_BYTES_BUDGET = 7 * (1024**3)

# Metal/MLX shared (unified-memory) buffer budget. Oversized shared buffers have
# been observed to sit in waitUntilCompleted / mx.eval with ~0% CPU — refuse early.
# Override via MONTE_NEO_METAL_SHARED_BYTES_BUDGET.
_DEFAULT_METAL_SHARED_BYTES_BUDGET = 384 * (1024**2)

# Hard bar cap for a single Metal economics dispatch (path-dependent kernel).
# 1M-class jobs have completed; 10M has hung — keep a conservative default.
# Override via MONTE_NEO_METAL_MAX_BARS.
_DEFAULT_METAL_MAX_BARS = 2_500_000


def research_bytes_budget(override: int | None = None) -> int:
    """Usable host research-buffer budget in bytes (default ~7 GiB)."""
    if override is not None:
        return max(1, int(override))
    raw = os.environ.get("MONTE_NEO_RESEARCH_BYTES_BUDGET", "").strip()
    if raw:
        return max(1, int(raw))
    return int(_DEFAULT_RESEARCH_BYTES_BUDGET)


def metal_shared_bytes_budget(override: int | None = None) -> int:
    """Max estimated Metal/MLX shared buffers before forced cpu_numba fallback."""
    if override is not None:
        return max(1, int(override))
    raw = os.environ.get("MONTE_NEO_METAL_SHARED_BYTES_BUDGET", "").strip()
    if raw:
        return max(1, int(raw))
    return int(_DEFAULT_METAL_SHARED_BYTES_BUDGET)


def metal_max_bars(override: int | None = None) -> int:
    """Max n_bars for a single Metal economics launch (no-hang guard)."""
    if override is not None:
        return max(1, int(override))
    raw = os.environ.get("MONTE_NEO_METAL_MAX_BARS", "").strip()
    if raw:
        return max(1, int(raw))
    return int(_DEFAULT_METAL_MAX_BARS)


def estimate_metal_shared_bytes(*, n_bars: int, n_combos: int) -> int:
    """Peak shared-buffer bytes for Metal research economics (float32/int32 path).

    Mirrors allocations in ``MetalResearchEngine.batch_terminal``: OHLC f32,
    signals i32, session i32, out f32, params f32.
    """
    n_bars = int(n_bars)
    n_combos = int(n_combos)
    ohlc = 4 * n_bars * 4
    signals = n_combos * n_bars * 4
    session = n_bars * 4
    out = n_combos * 4
    params = 13 * 4
    return int(ohlc + signals + session + out + params)


def plan_research_bytes(
    *,
    n_bars: int,
    n_combos: int,
    dtype_bytes: int = 8,
    include_ohlc: bool = True,
    include_signals: bool = True,
    include_equity: bool = False,
    bytes_budget: int | None = None,
) -> dict[str, Any]:
    """Rough peak resident estimate for a research batch + accelerator gates.

    Used for reports **and** as a hard no-hang guard before Metal/MLX.
    """
    if n_bars <= 0 or n_combos <= 0:
        raise ValueError("n_bars and n_combos must be positive")
    budget = research_bytes_budget(bytes_budget)
    ohlc = (4 * n_bars * dtype_bytes) if include_ohlc else 0
    signals = (n_combos * n_bars * 8) if include_signals else 0
    returns = n_combos * dtype_bytes
    equity = (n_combos * n_bars * dtype_bytes) if include_equity else 0
    peak = ohlc + signals + returns + equity
    tile_combos = n_combos
    if peak > budget and include_signals:
        per = max((n_bars * 8) + dtype_bytes, 1)
        remain = max(budget - ohlc, per)
        tile_combos = max(1, min(n_combos, int(remain // per)))
    metal_shared = estimate_metal_shared_bytes(n_bars=n_bars, n_combos=n_combos)
    metal_budget = metal_shared_bytes_budget()
    max_bars = metal_max_bars()
    metal_tile = n_combos
    if metal_shared > metal_budget and n_bars <= max_bars:
        # Tile combos so each Metal dispatch stays under the shared budget.
        per_combo = max(n_bars * 4, 1)
        fixed = (4 * n_bars * 4) + (n_bars * 4) + (13 * 4)
        remain = max(metal_budget - fixed, per_combo)
        metal_tile = max(1, min(n_combos, int(remain // per_combo)))
        metal_shared_tiled = estimate_metal_shared_bytes(n_bars=n_bars, n_combos=metal_tile)
    else:
        metal_shared_tiled = metal_shared
    fits_host = peak <= budget
    fits_metal = (n_bars <= max_bars) and (metal_shared_tiled <= metal_budget)
    return {
        "n_bars": int(n_bars),
        "n_combos": int(n_combos),
        "dtype_bytes": int(dtype_bytes),
        "bytes_peak_est": int(peak),
        "bytes_budget": int(budget),
        "fits_16gb_soft": bool(fits_host),
        "tile_combos_hint": int(tile_combos),
        "metal_shared_bytes_est": int(metal_shared),
        "metal_shared_bytes_budget": int(metal_budget),
        "metal_max_bars": int(max_bars),
        "metal_tile_combos_hint": int(metal_tile),
        "metal_shared_bytes_est_tiled": int(metal_shared_tiled),
        "fits_metal_shared": bool(fits_metal),
        "host_class": "apple_silicon_16gb",
    }


def decide_research_accelerator(
    *,
    n_bars: int,
    n_combos: int,
    device: str = "auto",
    bytes_budget: int | None = None,
) -> dict[str, Any]:
    """Decide whether Metal/MLX may run, or force transparent cpu_numba fallback.

    Returns keys: ``use_metal``, ``use_mlx``, ``fallback_reason``, ``plan``,
    ``metal_tile_combos``.
    """
    from monte_neo.oms.accel.device import resolve_device

    plan = plan_research_bytes(
        n_bars=n_bars, n_combos=n_combos, bytes_budget=bytes_budget
    )
    want = resolve_device(device)
    out: dict[str, Any] = {
        "want_device": want,
        "use_metal": False,
        "use_mlx": False,
        "fallback_reason": None,
        "plan": plan,
        "metal_tile_combos": int(plan["metal_tile_combos_hint"]),
    }
    if want == "cpu_numba":
        return out
    if not plan["fits_16gb_soft"]:
        out["fallback_reason"] = "research_bytes_budget_exceeded"
        return out
    if want == "metal":
        if int(n_bars) > int(plan["metal_max_bars"]):
            out["fallback_reason"] = "metal_max_bars_exceeded"
            return out
        if not plan["fits_metal_shared"]:
            out["fallback_reason"] = "metal_shared_bytes_budget_exceeded"
            return out
        out["use_metal"] = True
        return out
    if want == "mlx":
        # Same shared-memory class budget; MLX eval must not run unbounded on huge grids.
        if int(n_bars) > int(plan["metal_max_bars"]) or not plan["fits_metal_shared"]:
            out["fallback_reason"] = (
                "mlx_max_bars_exceeded"
                if int(n_bars) > int(plan["metal_max_bars"])
                else "mlx_shared_bytes_budget_exceeded"
            )
            return out
        out["use_mlx"] = True
        return out
    return out


__all__ = [
    "decide_research_accelerator",
    "estimate_metal_shared_bytes",
    "metal_max_bars",
    "metal_shared_bytes_budget",
    "plan_research_bytes",
    "research_bytes_budget",
]
