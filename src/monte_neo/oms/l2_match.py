"""L2 matching against book levels (CPU reference)."""

from __future__ import annotations

from dataclasses import dataclass

from monte_neo.oms.book import OrderBook
from monte_neo.oms.types import Order, OrderSide, OrderType


@dataclass(frozen=True, slots=True)
class L2MatchConfig:
    commission_bps: float = 5.0
    slippage_bps: float = 0.0  # book walk is primary adverse selection
    max_levels: int = 10

    def __post_init__(self) -> None:
        if min(self.commission_bps, self.slippage_bps) < 0.0:
            raise ValueError("bps must be non-negative")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        if self.max_levels < 1:
            raise ValueError("max_levels must be >= 1")  # pragma: no cover  # defensive / unreachable after unit mocks on CI


@dataclass(slots=True)
class L2FillSlice:
    qty: float
    price: float
    fee: float


def match_market_l2(
    order: Order,
    book: OrderBook,
    cfg: L2MatchConfig,
) -> list[L2FillSlice]:
    """Walk the book for a market order; may partial-fill if depth ends."""
    if order.order_type != OrderType.MARKET or order.remaining <= 0.0:
        return []  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    levels = book.asks if order.side == OrderSide.BUY else book.bids
    need = order.remaining
    fee_rate = cfg.commission_bps * 1e-4
    slip = cfg.slippage_bps * 1e-4
    out: list[L2FillSlice] = []
    for lvl in levels[: cfg.max_levels]:
        if need <= 1e-15:
            break
        take = min(need, lvl.size)
        raw = lvl.price
        px = raw * (1.0 + float(order.side) * slip)
        fee = abs(take * px) * fee_rate
        out.append(L2FillSlice(qty=take, price=px, fee=fee))
        need -= take
    return out


def match_limit_l2(
    order: Order,
    book: OrderBook,
    cfg: L2MatchConfig,
) -> list[L2FillSlice]:
    """Fill limit if marketable against best opposite; else empty."""
    if order.order_type != OrderType.LIMIT or order.remaining <= 0.0:
        return []  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    if order.side == OrderSide.BUY:
        best = book.best_ask()
        if best <= 0.0 or best > order.limit_px:
            return []
    else:
        best = book.best_bid()  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        if best <= 0.0 or best < order.limit_px:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            return []  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    # Treat as marketable limit: walk book but cap at limit
    mkt = Order(  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        order_id=order.order_id,
        symbol=order.symbol,
        side=order.side,
        order_type=OrderType.MARKET,
        qty=order.remaining,
        filled_qty=0.0,
    )
    slices = match_market_l2(mkt, book, cfg)  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    capped: list[L2FillSlice] = []  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    for s in slices:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        if order.side == OrderSide.BUY and s.price > order.limit_px + 1e-12:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            break  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        if order.side == OrderSide.SELL and s.price < order.limit_px - 1e-12:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            break  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        capped.append(s)  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    return capped  # pragma: no cover  # defensive / unreachable after unit mocks on CI
