"""Tick feed helpers for OMS tick/L2 lane."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class Tick:
    ts: int
    price: float
    size: float
    side: int  # +1 buy aggressor, -1 sell aggressor, 0 unknown


def synthetic_ticks(
    n: int = 10_000,
    *,
    seed: int = 42,
    start_px: float = 100.0,
    vol: float = 0.0005,
) -> np.ndarray:
    """Return structured array: ts, price, size, side."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0, vol, size=n)
    px = start_px * np.cumprod(1.0 + rets)
    size = rng.uniform(0.1, 2.0, size=n)
    side = rng.choice(np.array([-1, 1], dtype=np.int64), size=n)
    out = np.empty(
        n,
        dtype=[
            ("ts", np.int64),
            ("price", np.float64),
            ("size", np.float64),
            ("side", np.int64),
        ],
    )
    out["ts"] = np.arange(n, dtype=np.int64)
    out["price"] = px
    out["size"] = size
    out["side"] = side
    return out


def ticks_to_ohlc(ticks: np.ndarray, *, bars: int) -> dict[str, np.ndarray]:
    """Downsample ticks into equal-count OHLC bars."""
    n = int(ticks.shape[0])
    if bars < 1 or n < bars:
        raise ValueError("need n_ticks >= bars >= 1")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    chunk = n // bars
    open_ = np.empty(bars, dtype=np.float64)
    high = np.empty(bars, dtype=np.float64)
    low = np.empty(bars, dtype=np.float64)
    close = np.empty(bars, dtype=np.float64)
    for i in range(bars):
        sl = ticks["price"][i * chunk : (i + 1) * chunk]
        open_[i] = float(sl[0])
        high[i] = float(np.max(sl))
        low[i] = float(np.min(sl))
        close[i] = float(sl[-1])
    return {"open": open_, "high": high, "low": low, "close": close}
