"""Paper broker helpers for the OMS lane."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.oms.accel.device import AccelDevice
from monte_neo.oms.engine import OmsEngine
from monte_neo.oms.matching import MatchConfig
from monte_neo.oms.strategy import Strategy


class PaperBroker:
    """Thin wrapper around :class:`OmsEngine` for paper trading semantics."""

    def __init__(
        self,
        *,
        initial_cash: float = 100_000.0,
        commission_bps: float = 5.0,
        slippage_bps: float = 5.0,
        fill_policy: str = "next_bar_open",
        device: AccelDevice | str = "auto",
        symbol: str = "SYM",
        warmup_bars: int = 0,
    ) -> None:
        self.engine = OmsEngine(
            symbol=symbol,
            initial_cash=initial_cash,
            match=MatchConfig(
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
                fill_policy=fill_policy,
            ),
            device=device,
            warmup_bars=warmup_bars,
        )

    def run(
        self,
        open_: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        strategy: Strategy,
    ) -> dict[str, Any]:
        return self.engine.run(open_, high, low, close, strategy)


def run_oms_bar_backtest(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    strategy: Strategy,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience paper OMS bar backtest."""
    broker = PaperBroker(**kwargs)
    return broker.run(open_, high, low, close, strategy)
