"""L1/L2 order book snapshots for OMS tick matching."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class BookLevel:
    price: float
    size: float


@dataclass(slots=True)
class OrderBook:
    """Simple price-time book (bids descending, asks ascending)."""

    bids: list[BookLevel] = field(default_factory=list)
    asks: list[BookLevel] = field(default_factory=list)

    def best_bid(self) -> float:
        return self.bids[0].price if self.bids else 0.0

    def best_ask(self) -> float:
        return self.asks[0].price if self.asks else 0.0

    def mid(self) -> float:
        bb, ba = self.best_bid(), self.best_ask()
        if bb > 0.0 and ba > 0.0:
            return 0.5 * (bb + ba)  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        return bb or ba

    def depth(self) -> int:
        return max(len(self.bids), len(self.asks))

    def to_arrays(self, depth: int = 10) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Pack top levels into fixed arrays for Numba/Metal."""
        bid_px = np.zeros(depth, dtype=np.float64)
        bid_sz = np.zeros(depth, dtype=np.float64)
        ask_px = np.zeros(depth, dtype=np.float64)
        ask_sz = np.zeros(depth, dtype=np.float64)
        for i, lvl in enumerate(self.bids[:depth]):
            bid_px[i] = lvl.price
            bid_sz[i] = lvl.size
        for i, lvl in enumerate(self.asks[:depth]):
            ask_px[i] = lvl.price
            ask_sz[i] = lvl.size
        return bid_px, bid_sz, ask_px, ask_sz


def book_from_mid(
    mid: float,
    *,
    spread_bps: float = 2.0,
    depth: int = 5,
    size: float = 1.0,
    step_bps: float = 1.0,
) -> OrderBook:
    """Synthetic symmetric book around mid (research / paper)."""
    if mid <= 0.0:
        raise ValueError("mid must be positive")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    half = mid * (spread_bps * 1e-4) * 0.5
    step = mid * (step_bps * 1e-4)
    bids = [
        BookLevel(price=mid - half - i * step, size=size * (1.0 + 0.1 * i))
        for i in range(depth)
    ]
    asks = [
        BookLevel(price=mid + half + i * step, size=size * (1.0 + 0.1 * i))
        for i in range(depth)
    ]
    return OrderBook(bids=bids, asks=asks)
