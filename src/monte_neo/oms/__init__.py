"""OMS lane: event-driven paper order management (Apple Silicon ready)."""

from __future__ import annotations

from monte_neo.oms.blotter import Blotter
from monte_neo.oms.book import OrderBook, book_from_mid
from monte_neo.oms.engine import OmsEngine
from monte_neo.oms.l2_match import L2MatchConfig
from monte_neo.oms.paper import PaperBroker, run_oms_bar_backtest
from monte_neo.oms.strategy import SignalStrategy, Strategy
from monte_neo.oms.tick import synthetic_ticks, ticks_to_ohlc
from monte_neo.oms.tick_engine import TickL2Engine, run_tick_l2_market_buy
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
    "L2MatchConfig",
    "OmsEngine",
    "Order",
    "OrderBook",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PaperBroker",
    "Position",
    "SignalStrategy",
    "Strategy",
    "TickL2Engine",
    "book_from_mid",
    "run_oms_bar_backtest",
    "run_tick_l2_market_buy",
    "synthetic_ticks",
    "ticks_to_ohlc",
]
