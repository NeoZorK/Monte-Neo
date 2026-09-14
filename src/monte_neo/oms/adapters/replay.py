"""Replay recorded OHLC bars into paper OMS engine."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.oms.engine import OmsEngine
from monte_neo.oms.matching import MatchConfig
from monte_neo.oms.strategy import Strategy


def run_ohlc_replay(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    strategy: Strategy,
    *,
    symbol: str = "SYM",
    initial_cash: float = 100_000.0,
    match: MatchConfig | None = None,
    device: str = "auto",
    warmup_bars: int = 0,
) -> dict[str, Any]:
    """Drive OmsEngine from recorded OHLC (paper lane; no network)."""
    eng = OmsEngine(
        symbol=symbol,
        initial_cash=initial_cash,
        match=match,
        device=device,
        warmup_bars=warmup_bars,
    )
    out = eng.run(open_, high, low, close, strategy)
    out["lane"] = "oms_paper_replay"
    out["work_checklist"] = {
        **out.get("work_checklist", {}),
        "replay_adapter": True,
    }
    return out
