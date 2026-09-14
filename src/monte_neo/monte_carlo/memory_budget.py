"""M1 Pro 16GB-class Monte Carlo memory budgets (honest peak estimates)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Unified-memory host target #1: leave headroom for OS + Python + Metal/MLX runtime.
DEFAULT_HOST_BYTES = 16 * (1024**3)
DEFAULT_USABLE_BYTES = 10 * (1024**3)
# Conservative residency multiplier vs raw scenario OHLC float32 tensor.
OVERHEAD_FACTOR = 2.5
N_PRICE_FIELDS = 4  # OHL C residency for shuffle/noise scenario tensors


@dataclass(frozen=True)
class ScenarioBudget:
    """Peak-resident estimate and recommended tile size for scenario batches."""

    n_bars: int
    n_scenarios: int
    itemsize: int
    usable_bytes: int
    bytes_per_scenario: int
    bytes_peak_est: int
    tile_scenarios: int
    fits_in_one_tile: bool
    host_hint: str = "M1 Pro 16GB-class: tile scenarios to stay under usable budget"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def bytes_per_scenario(n_bars: int, *, itemsize: int = 4) -> int:
    """Estimated resident bytes for one scenario (OHLC + overhead)."""
    bars = max(1, int(n_bars))
    raw = bars * N_PRICE_FIELDS * int(itemsize)
    return int(raw * OVERHEAD_FACTOR)


def plan_scenario_budget(
    n_bars: int,
    n_scenarios: int,
    *,
    itemsize: int = 4,
    usable_bytes: int = DEFAULT_USABLE_BYTES,
) -> ScenarioBudget:
    """Plan tile size so peak residency stays within usable unified memory."""
    per = bytes_per_scenario(n_bars, itemsize=itemsize)
    n = max(0, int(n_scenarios))
    usable = max(per, int(usable_bytes))
    tile = max(1, usable // per) if n > 0 else 1
    if n > 0:
        tile = min(tile, n)
    peak = per * (tile if n > 0 else 0)
    return ScenarioBudget(
        n_bars=max(1, int(n_bars)),
        n_scenarios=n,
        itemsize=int(itemsize),
        usable_bytes=usable,
        bytes_per_scenario=per,
        bytes_peak_est=int(peak),
        tile_scenarios=int(tile),
        fits_in_one_tile=n <= tile,
    )


def iter_scenario_tiles(n_scenarios: int, tile_scenarios: int) -> list[tuple[int, int]]:
    """Return half-open [start, end) index ranges for scenario tiles."""
    n = max(0, int(n_scenarios))
    tile = max(1, int(tile_scenarios))
    return [(i, min(i + tile, n)) for i in range(0, n, tile)]
