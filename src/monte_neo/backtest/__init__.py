"""Professional fee-aware bar backtest engine (Monte-Neo)."""

from __future__ import annotations

from monte_neo.backtest.bar_engine import run_bar_backtest, run_strategy_backtest
from monte_neo.backtest.batch import run_bar_backtest_batch
from monte_neo.backtest.data import (
    ReplayBarSource,
    frame_to_ohlc,
    midprice_ticks_to_ohlc,
    synthetic_ohlcv,
    try_import_replay_inprocess,
)
from monte_neo.backtest.metrics import assert_fee_hurts_return, summarize_equity
from monte_neo.backtest.model import ExecutionModel
from monte_neo.backtest.portfolio_lite import run_multi_symbol_lite
from monte_neo.backtest.portfolio_shared import run_portfolio_shared_cash
from monte_neo.backtest.strategy import StrategySpec, build_signal
from monte_neo.backtest.sweep import run_sma_sweep, sma_signal, verify_sweep_matches_single

__all__ = [
    "ExecutionModel",
    "StrategySpec",
    "build_signal",
    "run_bar_backtest",
    "run_strategy_backtest",
    "run_bar_backtest_batch",
    "run_multi_symbol_lite",
    "run_portfolio_shared_cash",
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
