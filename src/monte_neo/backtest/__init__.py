"""Professional fee-aware bar backtest engine (Monte-Neo)."""

from __future__ import annotations

from monte_neo.backtest.bar_engine import run_bar_backtest
from monte_neo.backtest.data import (
    ReplayBarSource,
    frame_to_ohlc,
    midprice_ticks_to_ohlc,
    synthetic_ohlcv,
    try_import_replay_inprocess,
)
from monte_neo.backtest.metrics import assert_fee_hurts_return, summarize_equity
from monte_neo.backtest.model import ExecutionModel
from monte_neo.backtest.sweep import run_sma_sweep, sma_signal, verify_sweep_matches_single

__all__ = [
    "ExecutionModel",
    "run_bar_backtest",
    "run_sma_sweep",
    "sma_signal",
    "verify_sweep_matches_single",
    "frame_to_ohlc",
    "synthetic_ohlcv",
    "midprice_ticks_to_ohlc",
    "ReplayBarSource",
    "try_import_replay_inprocess",
    "summarize_equity",
    "assert_fee_hurts_return",
]
