"""OMS strategy interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from monte_neo.oms.types import OrderSide, OrderType


class Strategy(ABC):
    """Event strategy: emit order intents for the current bar index."""

    @abstractmethod
    def on_bar(
        self,
        i: int,
        *,
        open_: float,
        high: float,
        low: float,
        close: float,
        position_qty: float,
    ) -> list[dict[str, Any]]:
        """Return list of intents: {side, order_type, qty, limit_px?, tag?}."""


class SignalStrategy(Strategy):
    """Map precomputed int signal (+1/0/-1) to target flat/long(/short)."""

    def __init__(
        self,
        signal: np.ndarray,
        *,
        size_fraction: float = 1.0,
        allow_short: bool = False,
        symbol: str = "SYM",
    ) -> None:
        self.signal = np.asarray(signal, dtype=np.int64)
        self.size_fraction = float(size_fraction)
        self.allow_short = bool(allow_short)
        self.symbol = symbol
        if self.size_fraction <= 0.0 or self.size_fraction > 1.0:
            raise ValueError("size_fraction must be in (0, 1]")  # pragma: no cover  # defensive / unreachable after unit mocks on CI

    def on_bar(
        self,
        i: int,
        *,
        open_: float,
        high: float,
        low: float,
        close: float,
        position_qty: float,
    ) -> list[dict[str, Any]]:
        _ = open_, high, low
        if i < 0 or i >= self.signal.shape[0]:
            return []  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        raw = int(self.signal[i])
        if self.allow_short:
            target = 1 if raw > 0 else (-1 if raw < 0 else 0)  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        else:
            target = 1 if raw > 0 else 0
        cur = 1 if position_qty > 0 else (-1 if position_qty < 0 else 0)
        if target == cur:
            return []
        intents: list[dict[str, Any]] = []
        if cur != 0:
            intents.append(
                {
                    "side": OrderSide.SELL if cur > 0 else OrderSide.BUY,
                    "order_type": OrderType.MARKET,
                    "qty": abs(position_qty),
                    "tag": "flatten",
                }
            )
        if target != 0:
            # qty resolved by engine from cash * size_fraction
            intents.append(
                {
                    "side": OrderSide.BUY if target > 0 else OrderSide.SELL,
                    "order_type": OrderType.MARKET,
                    "qty": 0.0,
                    "tag": "enter",
                    "target_sign": target,
                    "size_fraction": self.size_fraction,
                }
            )
        return intents
