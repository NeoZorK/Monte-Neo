"""OCO / bracket helpers for paper OMS."""

from __future__ import annotations

from typing import TYPE_CHECKING

from monte_neo.oms.types import Order, OrderSide, OrderType, TimeInForce

if TYPE_CHECKING:
    from monte_neo.oms.engine import OmsEngine


def submit_bracket(
    engine: OmsEngine,
    *,
    side: OrderSide,
    qty: float,
    entry_type: OrderType = OrderType.MARKET,
    entry_limit: float = 0.0,
    take_profit: float,
    stop_loss: float,
    bar_index: int,
    tif: TimeInForce = TimeInForce.GTC,
) -> tuple[Order, Order, Order]:
    """Entry plus OCO take-profit / stop-loss exits (limit legs)."""
    if qty <= 0.0:
        raise ValueError("qty must be positive")
    if take_profit <= 0.0 or stop_loss <= 0.0:
        raise ValueError("take_profit and stop_loss must be positive")
    entry = engine.submit(
        {
            "side": side,
            "order_type": entry_type,
            "qty": qty,
            "limit_px": entry_limit,
            "tag": "bracket_entry",
            "tif": tif,
        },
        bar_index=bar_index,
    )
    exit_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
    group = engine.alloc_oco_group()
    tp = engine.submit(
        {
            "side": exit_side,
            "order_type": OrderType.LIMIT,
            "qty": qty,
            "limit_px": take_profit,
            "tag": "bracket_tp",
            "tif": TimeInForce.GTC,
            "oco_group": group,
        },
        bar_index=bar_index,
    )
    sl = engine.submit(
        {
            "side": exit_side,
            "order_type": OrderType.LIMIT,
            "qty": qty,
            "limit_px": stop_loss,
            "tag": "bracket_sl",
            "tif": TimeInForce.GTC,
            "oco_group": group,
        },
        bar_index=bar_index,
    )
    return entry, tp, sl
