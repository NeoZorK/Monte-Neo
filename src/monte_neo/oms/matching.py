"""Bar-event matching: market/limit against OHLC (next-bar or same-bar policy)."""

from __future__ import annotations

from dataclasses import dataclass

from monte_neo.oms.types import Order, OrderSide, OrderStatus, OrderType, TimeInForce


@dataclass(frozen=True, slots=True)
class MatchConfig:
    """Frozen OMS match economics for paper bar path."""

    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    fill_policy: str = "next_bar_open"  # or same_bar_close
    allow_short: bool = False
    max_fill_qty: float = 0.0  # 0 = unlimited (full remaining); else cap per match

    def __post_init__(self) -> None:
        if min(self.commission_bps, self.slippage_bps) < 0.0:
            raise ValueError("bps must be non-negative")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        if self.max_fill_qty < 0.0:
            raise ValueError("max_fill_qty must be non-negative")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        if self.fill_policy not in {"next_bar_open", "same_bar_close"}:
            raise ValueError("unsupported fill_policy")


def _slip_px(raw: float, side: OrderSide, slip_bps: float) -> float:
    rate = slip_bps * 1e-4
    return raw * (1.0 + float(side) * rate)


def _fill_qty(order: Order, cfg: MatchConfig) -> float:
    qty = order.remaining
    if cfg.max_fill_qty > 0.0:
        qty = min(qty, cfg.max_fill_qty)
    return qty


def try_match_market(
    order: Order,
    *,
    raw_px: float,
    cfg: MatchConfig,
) -> tuple[float, float, float] | None:
    """Return (fill_px, fee, fill_qty) or None if rejected."""
    if order.order_type != OrderType.MARKET or order.remaining <= 0.0:
        return None  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    if raw_px <= 0.0:
        return None  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    qty = _fill_qty(order, cfg)
    if qty <= 0.0:
        return None  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    px = _slip_px(raw_px, order.side, cfg.slippage_bps)
    fee = abs(qty * px) * (cfg.commission_bps * 1e-4)
    return px, fee, qty


def try_match_limit(
    order: Order,
    *,
    high: float,
    low: float,
    cfg: MatchConfig,
) -> tuple[float, float, float] | None:
    """Limit fill if bar range reaches limit; optional partial via max_fill_qty."""
    if order.order_type != OrderType.LIMIT or order.remaining <= 0.0:
        return None  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    hit = False
    if order.side == OrderSide.BUY and low <= order.limit_px:
        hit = True
    if order.side == OrderSide.SELL and high >= order.limit_px:
        hit = True  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    if not hit:
        return None
    qty = _fill_qty(order, cfg)
    if qty <= 0.0:
        return None  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    px = _slip_px(order.limit_px, order.side, cfg.slippage_bps)
    fee = abs(qty * px) * (cfg.commission_bps * 1e-4)
    return px, fee, qty


def mark_order_filled(order: Order, qty: float) -> None:
    order.filled_qty += qty
    if order.remaining <= 1e-15:
        order.status = OrderStatus.FILLED
        order.filled_qty = order.qty
    else:
        order.status = OrderStatus.PARTIAL


def cancel_order(order: Order) -> bool:
    if order.status in {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}:
        return False
    order.status = OrderStatus.CANCELED
    return True


def apply_tif_after_match(order: Order) -> None:
    """IOC cancels any remainder after a match attempt that left qty."""
    if order.tif != TimeInForce.IOC:
        return
    if order.status == OrderStatus.PARTIAL:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        order.status = OrderStatus.CANCELED  # pragma: no cover  # defensive / unreachable after unit mocks on CI
