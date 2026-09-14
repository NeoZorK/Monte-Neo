"""Tick/L2 paper OMS engine (event loop over ticks + synthetic books)."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.oms.accel.device import AccelDevice, resolve_device
from monte_neo.oms.blotter import Blotter
from monte_neo.oms.book import OrderBook, book_from_mid
from monte_neo.oms.l2_match import L2FillSlice, L2MatchConfig, match_limit_l2, match_market_l2
from monte_neo.oms.portfolio import apply_fill
from monte_neo.oms.types import (
    AccountState,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)


class TickL2Engine:
    """Paper OMS: rebuild book from mid each tick; match working orders."""

    def __init__(
        self,
        *,
        symbol: str = "SYM",
        initial_cash: float = 100_000.0,
        l2: L2MatchConfig | None = None,
        spread_bps: float = 2.0,
        book_depth: int = 5,
        device: AccelDevice | str = "auto",
        use_numba_walk: bool = True,
    ) -> None:
        self.symbol = symbol
        self.l2 = l2 or L2MatchConfig()
        self.spread_bps = float(spread_bps)
        self.book_depth = int(book_depth)
        self.device = resolve_device(device)
        self.use_numba_walk = bool(use_numba_walk)
        self.account = AccountState(cash=initial_cash, initial_cash=initial_cash)
        self.blotter = Blotter()
        self._next_order_id = 1
        self._next_fill_id = 1
        self._working: list[Order] = []

    def submit_market(self, side: OrderSide, qty: float, *, tag: str = "") -> Order:
        order = Order(
            order_id=self._next_order_id,
            symbol=self.symbol,
            side=side,
            order_type=OrderType.MARKET,
            qty=float(qty),
            tag=tag,
        )
        self._next_order_id += 1
        self.blotter.record_order(order)
        self._working.append(order)
        return order

    def submit_limit(
        self, side: OrderSide, qty: float, limit_px: float, *, tag: str = ""
    ) -> Order:
        order = Order(
            order_id=self._next_order_id,
            symbol=self.symbol,
            side=side,
            order_type=OrderType.LIMIT,
            qty=float(qty),
            limit_px=float(limit_px),
            tag=tag,
        )
        self._next_order_id += 1
        self.blotter.record_order(order)
        self._working.append(order)
        return order

    def _apply_slices(self, order: Order, slices: list[L2FillSlice], tick_i: int) -> None:
        for sl in slices:
            order.filled_qty += sl.qty
            if order.remaining <= 1e-15:
                order.status = OrderStatus.FILLED
                order.filled_qty = order.qty
            else:
                order.status = OrderStatus.PARTIAL
            fill = Fill(
                fill_id=self._next_fill_id,
                order_id=order.order_id,
                symbol=self.symbol,
                side=order.side,
                qty=sl.qty,
                price=sl.price,
                fee=sl.fee,
                bar_index=tick_i,
                reason="l2",
            )
            self._next_fill_id += 1
            self.blotter.record_fill(fill)
            apply_fill(self.account, fill)

    def _match_one(self, order: Order, book: OrderBook, tick_i: int) -> None:
        if order.status in {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}:
            return
        if self.use_numba_walk and order.order_type == OrderType.MARKET:
            bid_px, bid_sz, ask_px, ask_sz = book.to_arrays(self.l2.max_levels)
            from monte_neo.oms.accel.metal_dispatch import run_l2_walk

            walked = run_l2_walk(
                int(order.side),
                order.remaining,
                bid_px,
                bid_sz,
                ask_px,
                ask_sz,
                commission_bps=self.l2.commission_bps,
                slip_bps=self.l2.slippage_bps,
                device=self.device,
            )
            filled = float(walked["filled"])
            vwap = float(walked["vwap"])
            fee = float(walked["fee"])
            if filled <= 0.0:
                return
            self._apply_slices(
                order, [L2FillSlice(qty=filled, price=vwap, fee=fee)], tick_i
            )
            return
        slices = (
            match_market_l2(order, book, self.l2)
            if order.order_type == OrderType.MARKET
            else match_limit_l2(order, book, self.l2)
        )
        if slices:
            self._apply_slices(order, slices, tick_i)

    def run_ticks(self, ticks: np.ndarray) -> dict[str, Any]:
        if ticks.dtype.names is None or "price" not in ticks.dtype.names:
            raise ValueError("ticks must be structured with price field")
        n = int(ticks.shape[0])
        equity = np.empty(n, dtype=np.float64)
        peak = self.account.initial_cash
        max_dd = 0.0
        for i in range(n):
            mid = float(ticks["price"][i])
            book = book_from_mid(
                mid, spread_bps=self.spread_bps, depth=self.book_depth
            )
            still: list[Order] = []
            for order in self._working:
                self._match_one(order, book, i)
                if order.status not in {
                    OrderStatus.FILLED,
                    OrderStatus.CANCELED,
                    OrderStatus.REJECTED,
                }:
                    still.append(order)
            self._working = still
            eq = self.account.equity({self.symbol: mid})
            equity[i] = eq
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        final_eq = float(equity[-1]) if n else float(self.account.cash)
        return {
            "ok": True,
            "engine": "monte_neo.oms.tick_l2",
            "lane": "oms_tick_l2",
            "device": self.device,
            "n_ticks": n,
            "total_return": float(final_eq / self.account.initial_cash - 1.0),
            "max_drawdown": float(max_dd),
            "final_cash": float(self.account.cash),
            "equity": equity,
            "account": self.account.to_dict(),
            "blotter": self.blotter.summary(),
            "work_checklist": {
                "tick_path": True,
                "l2_matching": True,
                "order_lifecycle": True,
                "fees": self.l2.commission_bps > 0.0,
                "blotter": True,
                "numba_book_walk": self.use_numba_walk,
                "metal_ready": self.device in {"metal", "auto"},
            },
        }


def run_tick_l2_market_buy(
    ticks: np.ndarray,
    *,
    qty: float,
    initial_cash: float = 100_000.0,
    commission_bps: float = 5.0,
    device: AccelDevice | str = "cpu_numba",
) -> dict[str, Any]:
    """Submit market buy before first tick, then process the feed."""
    eng = TickL2Engine(
        initial_cash=initial_cash,
        l2=L2MatchConfig(commission_bps=commission_bps),
        device=device,
    )
    eng.submit_market(OrderSide.BUY, qty, tag="mkt_buy")
    return eng.run_ticks(ticks)
