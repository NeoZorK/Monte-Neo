from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TradeResult:
    """Single trade result."""

    entry_idx: int
    exit_idx: int
    entry_price: float
    exit_price: float
    direction: int  # 1 = long, -1 = short
    pnl: float
    pnl_pct: float
