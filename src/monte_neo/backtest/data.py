"""OHLCV helpers and optional replay mid-price feeder adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

REQUIRED_COLS = ("open", "high", "low", "close")


def frame_to_ohlc(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Extract float64 OHLC arrays from a DataFrame."""
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    return {c: df[c].to_numpy(dtype=np.float64, copy=True) for c in REQUIRED_COLS}


def synthetic_ohlcv(n_bars: int = 5_000, seed: int = 42) -> pd.DataFrame:
    """Deterministic synthetic OHLCV for tests and private races."""
    rng = np.random.default_rng(seed + n_bars)
    dt = 1.0 / (60 * 24 * 365)
    mu, sigma = 0.05, 0.6
    rets = rng.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt), size=n_bars)
    close = 50_000.0 * np.exp(np.cumsum(rets))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    wiggle = rng.uniform(0.0001, 0.002, size=n_bars)
    high = np.maximum(open_, close) * (1.0 + wiggle)
    low = np.minimum(open_, close) * (1.0 - wiggle)
    volume = rng.uniform(1.0, 100.0, size=n_bars)
    ts = pd.date_range("2024-01-01", periods=n_bars, freq="min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def midprice_ticks_to_ohlc(
    bids: np.ndarray,
    asks: np.ndarray,
    *,
    bars: int,
) -> dict[str, np.ndarray]:
    """Build coarse OHLC from mid-prices (replay-style feeder, no Redis).

    Splits the mid series into ``bars`` equal chunks. Used for realism-path
    experiments; not required for hot-path Manifold-fair bar races.
    """
    bid = np.asarray(bids, dtype=np.float64)
    ask = np.asarray(asks, dtype=np.float64)
    if bid.shape != ask.shape or bid.ndim != 1 or bid.size < bars:
        raise ValueError("bids/asks must be 1-D with size >= bars")
    mid = 0.5 * (bid + ask)
    edges = np.linspace(0, mid.size, bars + 1, dtype=np.int64)
    open_ = np.empty(bars, dtype=np.float64)
    high = np.empty(bars, dtype=np.float64)
    low = np.empty(bars, dtype=np.float64)
    close = np.empty(bars, dtype=np.float64)
    for i in range(bars):
        chunk = mid[edges[i] : edges[i + 1]]
        open_[i] = chunk[0]
        high[i] = float(np.max(chunk))
        low[i] = float(np.min(chunk))
        close[i] = chunk[-1]
    return {"open": open_, "high": high, "low": low, "close": close}


@dataclass(frozen=True, slots=True)
class ReplayBarSource:
    """Optional in-process mid-price → OHLC feeder (Redis never on hot path).

    Accepts bid/ask tick arrays already in memory. Designed so private races can
    optionally inject realism bars without paying IPC to a replay Redis server.
    """

    bids: np.ndarray
    asks: np.ndarray

    def to_ohlc(self, bars: int) -> dict[str, np.ndarray]:
        return midprice_ticks_to_ohlc(self.bids, self.asks, bars=bars)

    @classmethod
    def from_synthetic_ticks(
        cls, *, n_ticks: int = 10_000, seed: int = 0
    ) -> ReplayBarSource:
        rng = np.random.default_rng(seed)
        mid = 100.0 + np.cumsum(rng.normal(0.0, 0.05, size=n_ticks))
        spread = 0.02
        bid = mid - 0.5 * spread
        ask = mid + 0.5 * spread
        return cls(bids=bid, asks=ask)


def try_import_replay_inprocess() -> dict[str, Any]:
    """Best-effort detect trading-data-replay-engine in-process mid-price helper."""
    try:
        from src.inprocess_midprice import vectorized_midprice  # type: ignore

        return {"ok": True, "symbol": "vectorized_midprice", "fn": vectorized_midprice}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
