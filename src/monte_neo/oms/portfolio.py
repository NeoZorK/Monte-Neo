"""OMS portfolio / account updates on fills."""

from __future__ import annotations

from monte_neo.oms.types import AccountState, Fill, OrderSide, Position


def apply_fill(account: AccountState, fill: Fill) -> None:
    """Apply a fill to cash and position (research-grade netting)."""
    pos = account.position(fill.symbol)
    signed = float(fill.side) * fill.qty
    notional = fill.qty * fill.price
    # Pay fee always
    account.cash -= fill.fee
    account.fees_paid += fill.fee

    if fill.side == OrderSide.BUY:
        account.cash -= notional
    else:
        account.cash += notional

    new_qty = pos.qty + signed
    if pos.qty == 0.0 or (pos.qty > 0.0) == (signed > 0.0):
        # Increasing or opening
        total = abs(pos.qty) * pos.avg_px + fill.qty * fill.price
        pos.avg_px = total / abs(new_qty) if new_qty != 0.0 else 0.0
        pos.qty = new_qty
        return

    # Reducing / flipping
    close_qty = min(abs(pos.qty), fill.qty)
    pnl = close_qty * (fill.price - pos.avg_px) * (1.0 if pos.qty > 0.0 else -1.0)
    account.realized_pnl += pnl
    if abs(new_qty) < 1e-15:
        pos.qty = 0.0
        pos.avg_px = 0.0
    elif (pos.qty > 0.0) != (new_qty > 0.0):
        # Flip residual
        pos.qty = new_qty
        pos.avg_px = fill.price
    else:
        pos.qty = new_qty


def mark_positions(account: AccountState, marks: dict[str, float]) -> float:
    return account.equity(marks)
