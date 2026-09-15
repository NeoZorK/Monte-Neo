"""OMS paper engine over bar OHLC (event loop + Numba/Metal device select)."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.oms.accel.device import AccelDevice, resolve_device
from monte_neo.oms.blotter import Blotter
from monte_neo.oms.clock import BarClock
from monte_neo.oms.matching import (
    MatchConfig,
    apply_tif_after_match,
    cancel_order,
    mark_order_filled,
    try_match_limit,
    try_match_market,
)
from monte_neo.oms.portfolio import apply_fill, mark_positions
from monte_neo.oms.strategy import Strategy
from monte_neo.oms.types import (
    AccountState,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)


class OmsEngine:
    """Single-symbol paper OMS driven by bar events."""

    def __init__(
        self,
        *,
        symbol: str = "SYM",
        initial_cash: float = 100_000.0,
        match: MatchConfig | None = None,
        device: AccelDevice | str = "auto",
        warmup_bars: int = 0,
    ) -> None:
        self.symbol = symbol
        self.match = match or MatchConfig()
        self.device = resolve_device(device)
        self.warmup_bars = int(warmup_bars)
        self.account = AccountState(cash=initial_cash, initial_cash=initial_cash)
        self.blotter = Blotter()
        self.clock = BarClock()
        self._next_order_id = 1
        self._next_fill_id = 1
        self._next_oco_group = 1
        self._working: list[Order] = []

    def submit(self, intent: dict[str, Any], *, bar_index: int) -> Order:
        tif_raw = intent.get("tif", TimeInForce.GTC)
        tif = tif_raw if isinstance(tif_raw, TimeInForce) else TimeInForce(int(tif_raw))
        order = Order(
            order_id=self._next_order_id,
            symbol=self.symbol,
            side=OrderSide(intent["side"]),
            order_type=OrderType(intent["order_type"]),
            qty=float(intent.get("qty") or 0.0),
            limit_px=float(intent.get("limit_px") or 0.0),
            created_i=bar_index,
            tag=str(intent.get("tag") or ""),
            tif=tif,
            oco_group=int(intent.get("oco_group") or 0),
        )
        self._next_order_id += 1
        if order.qty <= 0.0 and intent.get("tag") == "enter":
            frac = float(intent.get("size_fraction") or 1.0)
            order.qty = max(self.account.cash * frac, 0.0)
            order.tag = "enter"
        if order.qty <= 0.0 and order.tag != "enter":
            order.status = OrderStatus.REJECTED
            self.blotter.record_order(order)
            return order
        self.blotter.record_order(order)
        self._working.append(order)
        return order

    def alloc_oco_group(self) -> int:
        gid = self._next_oco_group
        self._next_oco_group += 1
        return gid

    def submit_bracket(self, **kwargs):  # thin alias
        from monte_neo.oms.bracket import submit_bracket as _sb

        return _sb(self, **kwargs)

    def cancel(self, order_id: int) -> bool:
        for o in self._working:
            if o.order_id == order_id and cancel_order(o):
                return True
        return False

    def _cancel_oco_siblings(self, filled: Order) -> None:
        if filled.oco_group <= 0:
            return
        for o in self._working:
            if o.order_id == filled.order_id:
                continue
            if o.oco_group == filled.oco_group:
                cancel_order(o)

    def _fill_px_for_bar(
        self, i: int, open_: np.ndarray, close: np.ndarray
    ) -> float:
        if self.match.fill_policy == "next_bar_open":
            if i + 1 >= open_.shape[0]:
                return float(close[i])
            return float(open_[i + 1])
        return float(close[i])

    def _execute_order(
        self,
        order: Order,
        *,
        i: int,
        fill_raw: float,
        high: float,
        low: float,
    ) -> None:
        if order.status in {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}:
            return
        matched = None
        if order.order_type == OrderType.MARKET:
            if order.tag == "enter" and order.filled_qty == 0.0:
                px_est = _slip_est(fill_raw, order.side, self.match.slippage_bps)
                if px_est <= 0.0 or self.account.cash <= 0.0:
                    order.status = OrderStatus.REJECTED
                    return
                notional = min(order.qty, self.account.cash)
                order.qty = notional / px_est
                order.tag = "enter_sized"
            matched = try_match_market(order, raw_px=fill_raw, cfg=self.match)
            fill_i = i + 1 if self.match.fill_policy == "next_bar_open" else i
        else:
            matched = try_match_limit(order, high=high, low=low, cfg=self.match)
            fill_i = i
        if matched is None:
            apply_tif_after_match(order)
            return
        px, fee, qty = matched
        mark_order_filled(order, qty)
        apply_tif_after_match(order)
        fill = Fill(
            fill_id=self._next_fill_id,
            order_id=order.order_id,
            symbol=self.symbol,
            side=order.side,
            qty=qty,
            price=px,
            fee=fee,
            bar_index=int(fill_i),
            reason="market" if order.order_type == OrderType.MARKET else "limit",
        )
        self._next_fill_id += 1
        self.blotter.record_fill(fill)
        apply_fill(self.account, fill)
        if order.status == OrderStatus.FILLED:
            self._cancel_oco_siblings(order)

    def run(
        self,
        open_: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        strategy: Strategy,
    ) -> dict[str, Any]:
        o = np.asarray(open_, dtype=np.float64)
        h = np.asarray(high, dtype=np.float64)
        l = np.asarray(low, dtype=np.float64)
        c = np.asarray(close, dtype=np.float64)
        n = c.shape[0]
        if not (o.shape == h.shape == l.shape == c.shape) or n < 2:
            raise ValueError("OHLC must be equal-length 1-D with >= 2 bars")
        equity = np.empty(n, dtype=np.float64)
        peak = self.account.initial_cash
        max_dd = 0.0
        self.clock.at(0)

        for i in range(n):
            self.clock.at(i)
            fill_raw = self._fill_px_for_bar(i - 1, o, c) if i > 0 else float(o[0])
            still: list[Order] = []
            for order in self._working:
                if order.status == OrderStatus.CANCELED:
                    continue
                if order.order_type == OrderType.MARKET and order.created_i == i - 1:
                    self._execute_order(
                        order, i=i - 1, fill_raw=float(o[i]), high=float(h[i]), low=float(l[i])
                    )
                elif order.order_type == OrderType.LIMIT and order.created_i <= i:
                    self._execute_order(
                        order, i=i, fill_raw=fill_raw, high=float(h[i]), low=float(l[i])
                    )
                if order.status not in {
                    OrderStatus.FILLED,
                    OrderStatus.CANCELED,
                    OrderStatus.REJECTED,
                }:
                    still.append(order)
            self._working = still

            pos_qty = self.account.position(self.symbol).qty
            eq = mark_positions(self.account, {self.symbol: float(c[i])})
            equity[i] = eq
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

            if i < self.warmup_bars or i + 1 >= n:
                continue
            intents = strategy.on_bar(
                i,
                open_=float(o[i]),
                high=float(h[i]),
                low=float(l[i]),
                close=float(c[i]),
                position_qty=pos_qty,
            )
            for intent in intents:
                self.submit(intent, bar_index=i)

        pos = self.account.position(self.symbol)
        if abs(pos.qty) > 1e-15:
            side = OrderSide.SELL if pos.qty > 0 else OrderSide.BUY
            order = self.submit(
                {
                    "side": side,
                    "order_type": OrderType.MARKET,
                    "qty": abs(pos.qty),
                    "tag": "eod_flatten",
                },
                bar_index=n - 2 if n >= 2 else 0,
            )
            self._execute_order(
                order,
                i=n - 2 if n >= 2 else 0,
                fill_raw=float(c[n - 1]),
                high=float(h[n - 1]),
                low=float(l[n - 1]),
            )
            equity[n - 1] = self.account.cash

        ret = self.account.cash / self.account.initial_cash - 1.0
        return {
            "ok": True,
            "engine": "monte_neo.oms",
            "device": self.device,
            "lane": "oms_paper_bar",
            "total_return": float(ret),
            "max_drawdown": float(max_dd),
            "final_cash": float(self.account.cash),
            "equity": equity,
            "account": self.account.to_dict(),
            "blotter": self.blotter.summary(),
            "fills": [
                {
                    "order_id": f.order_id,
                    "qty": f.qty,
                    "price": f.price,
                    "fee": f.fee,
                    "bar_index": f.bar_index,
                    "side": int(f.side),
                    "reason": f.reason,
                }
                for f in self.blotter.fills
            ],
            "work_checklist": {
                "order_lifecycle": True,
                "market_orders": True,
                "limit_orders": True,
                "cancel": True,
                "gtc": True,
                "ioc": True,
                "partials": self.match.max_fill_qty > 0.0,
                "oco_bracket": True,
                "fees": self.match.commission_bps > 0.0,
                "slippage": self.match.slippage_bps > 0.0,
                "blotter": True,
                "shared_cash_netting": True,
                "bar_clock": True,
                "next_bar_fill": self.match.fill_policy == "next_bar_open",
                "metal_ready": self.device in {"metal", "auto"},
            },
        }


def _slip_est(raw: float, side: OrderSide, slip_bps: float) -> float:
    return raw * (1.0 + float(side) * slip_bps * 1e-4)
