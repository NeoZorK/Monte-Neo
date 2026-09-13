"""OMS lane: event-driven paper order management (Apple Silicon ready)."""

from __future__ import annotations

from monte_neo.oms.blotter import Blotter
from monte_neo.oms.engine import OmsEngine
from monte_neo.oms.paper import PaperBroker, run_oms_bar_backtest
from monte_neo.oms.strategy import SignalStrategy, Strategy
from monte_neo.oms.types import (
    AccountState,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
)

__all__ = [
    "AccountState",
    "Blotter",
    "Fill",
    "OmsEngine",
    "Order",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PaperBroker",
    "Position",
    "SignalStrategy",
    "Strategy",
    "run_oms_bar_backtest",
]
