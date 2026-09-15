"""M1 Pro 16GB-class research memory planning (estimates only)."""

from __future__ import annotations

from typing import Any


def plan_research_bytes(
    *,
    n_bars: int,
    n_combos: int,
    dtype_bytes: int = 8,
    include_ohlc: bool = True,
    include_signals: bool = True,
    include_equity: bool = False,
) -> dict[str, Any]:
    """Rough peak resident estimate for a research batch.

    Not a hard allocator — used for reports and 16GB-safe tiling hints.
    """
    if n_bars <= 0 or n_combos <= 0:
        raise ValueError("n_bars and n_combos must be positive")
    ohlc = (4 * n_bars * dtype_bytes) if include_ohlc else 0
    signals = (n_combos * n_bars * 8) if include_signals else 0
    returns = n_combos * dtype_bytes
    equity = (n_combos * n_bars * dtype_bytes) if include_equity else 0
    peak = ohlc + signals + returns + equity
    budget = 12 * (1024**3)
    tile_combos = n_combos
    if peak > budget and include_signals:
        per = max((n_bars * 8) + dtype_bytes, 1)
        remain = max(budget - ohlc, per)
        tile_combos = max(1, min(n_combos, int(remain // per)))
    return {
        "n_bars": int(n_bars),
        "n_combos": int(n_combos),
        "dtype_bytes": int(dtype_bytes),
        "bytes_peak_est": int(peak),
        "bytes_budget": int(budget),
        "fits_16gb_soft": bool(peak <= budget),
        "tile_combos_hint": int(tile_combos),
        "host_class": "apple_silicon_16gb",
    }


__all__ = ["plan_research_bytes"]
