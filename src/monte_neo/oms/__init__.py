"""OMS lane: event-driven paper order management (Apple Silicon ready)."""

from __future__ import annotations

from monte_neo.oms.accel import preferred_compute_device, run_batch_terminal, run_l2_walk_batch
from monte_neo.oms.adapters import make_adapter, run_ohlc_replay
from monte_neo.oms.adapters.base import FillReport, OrderIntent, OrderReport
from monte_neo.oms.adapters.binance import BinanceAdapter
from monte_neo.oms.adapters.bybit import BybitAdapter
from monte_neo.oms.adapters.paper_exchange import PaperExchangeAdapter
from monte_neo.oms.adapters.reconcile import reconcile_fills
from monte_neo.oms.blotter import Blotter
from monte_neo.oms.book import OrderBook, book_from_mid
from monte_neo.oms.bracket import submit_bracket
from monte_neo.oms.clock import BarClock
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
    TimeInForce,
)

__all__ = [
    "AccountState",
    "BarClock",
    "BinanceAdapter",
    "Blotter",
    "BybitAdapter",
    "Fill",
    "FillReport",
    "L2MatchConfig",
    "OmsEngine",
    "Order",
    "OrderBook",
    "OrderIntent",
    "OrderReport",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PaperBroker",
    "PaperExchangeAdapter",
    "Position",
    "SignalStrategy",
    "Strategy",
    "TickL2Engine",
    "TimeInForce",
    "book_from_mid",
    "make_adapter",
    "run_ohlc_replay",
    "submit_bracket",
    "preferred_compute_device",
    "reconcile_fills",
    "run_batch_terminal",
    "run_l2_walk_batch",
    "run_oms_bar_backtest",
    "run_tick_l2_market_buy",
    "synthetic_ticks",
    "ticks_to_ohlc",
]
