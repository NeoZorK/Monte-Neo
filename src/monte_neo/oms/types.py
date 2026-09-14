"""OMS domain types (orders, fills, positions, account)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class OrderSide(IntEnum):
    BUY = 1
    SELL = -1


class OrderType(IntEnum):
    MARKET = 1
    LIMIT = 2


class OrderStatus(IntEnum):
    NEW = 1
    PARTIAL = 2
    FILLED = 3
    CANCELED = 4
    REJECTED = 5


class TimeInForce(IntEnum):
    """Order lifetime. GTC rests until fill or cancel; IOC cancels remainder."""

    GTC = 1
    IOC = 2


@dataclass(slots=True)
class Order:
    order_id: int
    symbol: str
    side: OrderSide
    order_type: OrderType
    qty: float
    limit_px: float = 0.0
    status: OrderStatus = OrderStatus.NEW
    filled_qty: float = 0.0
    created_i: int = 0
    tag: str = ""
    tif: TimeInForce = TimeInForce.GTC
    oco_group: int = 0  # 0 = none; shared id links OCO/bracket exits

    @property
    def remaining(self) -> float:
        return max(0.0, self.qty - self.filled_qty)


@dataclass(slots=True)
class Fill:
    fill_id: int
    order_id: int
    symbol: str
    side: OrderSide
    qty: float
    price: float
    fee: float
    bar_index: int
    reason: str = "match"


@dataclass(slots=True)
class Position:
    symbol: str
    qty: float = 0.0
    avg_px: float = 0.0

    @property
    def side_sign(self) -> int:
        if self.qty > 0.0:
            return 1
        if self.qty < 0.0:
            return -1
        return 0


@dataclass(slots=True)
class AccountState:
    cash: float
    initial_cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    fees_paid: float = 0.0

    def position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]

    def equity(self, marks: dict[str, float]) -> float:
        eq = self.cash
        for sym, pos in self.positions.items():
            eq += pos.qty * float(marks.get(sym, pos.avg_px))
        return eq

    def to_dict(self) -> dict[str, Any]:
        return {
            "cash": self.cash,
            "initial_cash": self.initial_cash,
            "realized_pnl": self.realized_pnl,
            "fees_paid": self.fees_paid,
            "positions": {
                s: {"qty": p.qty, "avg_px": p.avg_px} for s, p in self.positions.items()
            },
        }
