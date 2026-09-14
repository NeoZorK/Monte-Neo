"""Broker adapter protocol for paper/live OMS gateways."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from monte_neo.oms.types import OrderSide, OrderType


@dataclass(slots=True)
class OrderIntent:
    symbol: str
    side: OrderSide
    order_type: OrderType
    qty: float
    limit_px: float = 0.0
    client_order_id: str = ""
    tag: str = ""


@dataclass(slots=True)
class OrderReport:
    venue_order_id: str
    client_order_id: str
    symbol: str
    status: str
    qty: float
    filled_qty: float = 0.0
    avg_px: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FillReport:
    venue_fill_id: str
    venue_order_id: str
    symbol: str
    side: OrderSide
    qty: float
    price: float
    fee: float
    ts: int = 0


class BrokerAdapter(Protocol):
    """Unified submit/cancel/query + fills stream."""

    name: str
    mode: str  # paper | live

    def submit(self, intent: OrderIntent) -> OrderReport: ...

    def cancel(self, venue_order_id: str) -> bool: ...

    def poll_fills(self) -> list[FillReport]: ...

    def get_balances(self) -> dict[str, float]: ...

    def get_positions(self) -> dict[str, float]: ...

    def work_checklist(self) -> dict[str, bool]: ...
