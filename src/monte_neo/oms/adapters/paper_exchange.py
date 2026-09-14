"""Local paper exchange adapter (no network)."""

from __future__ import annotations

from typing import Any

from monte_neo.oms.adapters.base import FillReport, OrderIntent, OrderReport
from monte_neo.oms.book import book_from_mid
from monte_neo.oms.l2_match import L2MatchConfig, match_limit_l2, match_market_l2
from monte_neo.oms.types import Order, OrderSide, OrderStatus, OrderType


class PaperExchangeAdapter:
    """In-process paper venue: match against a synthetic mid book."""

    name = "paper"
    mode = "paper"

    def __init__(
        self,
        *,
        initial_cash: float = 100_000.0,
        mid: float = 100.0,
        commission_bps: float = 5.0,
        spread_bps: float = 2.0,
        book_depth: int = 5,
    ) -> None:
        self.cash = float(initial_cash)
        self.mid = float(mid)
        self.spread_bps = float(spread_bps)
        self.book_depth = int(book_depth)
        self.l2 = L2MatchConfig(commission_bps=commission_bps)
        self._positions: dict[str, float] = {}
        self._orders: dict[str, Order] = {}
        self._pending_fills: list[FillReport] = []
        self._next_id = 1
        self._next_fill = 1

    def set_mid(self, mid: float) -> None:
        if mid <= 0.0:
            raise ValueError("mid must be positive")
        self.mid = float(mid)

    def submit(self, intent: OrderIntent) -> OrderReport:
        oid = f"PAPER-{self._next_id}"
        self._next_id += 1
        order = Order(
            order_id=self._next_id,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            qty=float(intent.qty),
            limit_px=float(intent.limit_px),
            tag=intent.tag,
        )
        self._orders[oid] = order
        book = book_from_mid(
            self.mid, spread_bps=self.spread_bps, depth=self.book_depth
        )
        slices = (
            match_market_l2(order, book, self.l2)
            if intent.order_type == OrderType.MARKET
            else match_limit_l2(order, book, self.l2)
        )
        filled = 0.0
        notional = 0.0
        fee_sum = 0.0
        for sl in slices:
            filled += sl.qty
            notional += sl.qty * sl.price
            fee_sum += sl.fee
            self._pending_fills.append(
                FillReport(
                    venue_fill_id=f"PF-{self._next_fill}",
                    venue_order_id=oid,
                    symbol=intent.symbol,
                    side=intent.side,
                    qty=sl.qty,
                    price=sl.price,
                    fee=sl.fee,
                )
            )
            self._next_fill += 1
            self._apply_cash_pos(intent.symbol, intent.side, sl.qty, sl.price, sl.fee)
        order.filled_qty = filled
        if filled <= 0.0:
            status = "NEW" if intent.order_type == OrderType.LIMIT else "REJECTED"
            if status == "REJECTED":
                order.status = OrderStatus.REJECTED
        elif filled + 1e-15 >= order.qty:
            order.status = OrderStatus.FILLED
            status = "FILLED"
        else:
            order.status = OrderStatus.PARTIAL
            status = "PARTIAL"
        avg = (notional / filled) if filled > 0 else 0.0
        return OrderReport(
            venue_order_id=oid,
            client_order_id=intent.client_order_id or oid,
            symbol=intent.symbol,
            status=status,
            qty=order.qty,
            filled_qty=filled,
            avg_px=avg,
        )

    def _apply_cash_pos(
        self, symbol: str, side: OrderSide, qty: float, px: float, fee: float
    ) -> None:
        self.cash -= fee
        signed = float(side) * qty
        if side == OrderSide.BUY:
            self.cash -= qty * px
        else:
            self.cash += qty * px
        self._positions[symbol] = self._positions.get(symbol, 0.0) + signed

    def cancel(self, venue_order_id: str) -> bool:
        order = self._orders.get(venue_order_id)
        if order is None:
            return False
        if order.status in {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}:
            return False
        order.status = OrderStatus.CANCELED
        return True

    def poll_fills(self) -> list[FillReport]:
        out = list(self._pending_fills)
        self._pending_fills.clear()
        return out

    def get_balances(self) -> dict[str, float]:
        return {"cash": self.cash}

    def get_positions(self) -> dict[str, float]:
        return dict(self._positions)

    def work_checklist(self) -> dict[str, bool]:
        return {
            "paper": True,
            "live": False,
            "submit": True,
            "cancel": True,
            "poll_fills": True,
            "no_network": True,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "balances": self.get_balances(),
            "positions": self.get_positions(),
            "n_orders": len(self._orders),
        }
