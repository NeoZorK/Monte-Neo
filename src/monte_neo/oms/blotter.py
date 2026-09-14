"""Blotter: append-only order/fill journal for OMS."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from monte_neo.oms.types import Fill, Order


@dataclass(slots=True)
class Blotter:
    orders: list[Order] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)

    def record_order(self, order: Order) -> None:
        self.orders.append(order)

    def record_fill(self, fill: Fill) -> None:
        self.fills.append(fill)

    def fills_for_order(self, order_id: int) -> list[Fill]:
        return [f for f in self.fills if f.order_id == order_id]

    def summary(self) -> dict[str, Any]:
        return {
            "n_orders": len(self.orders),
            "n_fills": len(self.fills),
            "n_canceled": sum(1 for o in self.orders if o.status.name == "CANCELED"),
            "n_filled": sum(1 for o in self.orders if o.status.name == "FILLED"),
        }
