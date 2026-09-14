"""Factory for OMS venue adapters."""

from __future__ import annotations

from typing import Any

from monte_neo.oms.adapters.binance import BinanceAdapter
from monte_neo.oms.adapters.bybit import BybitAdapter
from monte_neo.oms.adapters.paper_exchange import PaperExchangeAdapter


def make_adapter(
    venue: str = "paper",
    *,
    mode: str = "paper",
    **kwargs: Any,
) -> PaperExchangeAdapter | BinanceAdapter | BybitAdapter:
    """Create a venue adapter. Live mode is env-gated inside venue classes."""
    v = str(venue).lower()
    if v == "paper":
        if mode != "paper":
            raise ValueError("paper venue only supports mode=paper")
        return PaperExchangeAdapter(**kwargs)
    if v == "binance":
        return BinanceAdapter(mode=mode, **kwargs)
    if v == "bybit":
        return BybitAdapter(mode=mode, **kwargs)
    raise ValueError(f"unsupported venue: {venue}")
