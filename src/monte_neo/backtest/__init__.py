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
from monte_neo.backtest.export import (
    EXPORT_API_VERSION,
    export_batch,
    export_single,
    export_sma_signal,
    export_sma_sweep,
    research_manifest,
    verify_export_golden,
)
from monte_neo.backtest.golden import (
    golden_fixture,
    verify_golden_vectors,
)
from monte_neo.backtest.memory_plan import decide_research_accelerator, plan_research_bytes
from monte_neo.backtest.metal_economics import (
    get_metal_research_engine,
    metal_economics_eligible,
)
from monte_neo.backtest.metrics import assert_fee_hurts_return, summarize_equity
from monte_neo.backtest.model import ExecutionModel
from monte_neo.backtest.portfolio_lite import run_multi_symbol_lite
from monte_neo.backtest.portfolio_shared import run_portfolio_shared_cash
from monte_neo.backtest.signal_factory import build_sma_cross_grid, build_sma_cross_grid_numba_golden
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
    "metal_economics_eligible",
    "get_metal_research_engine",
    "frame_to_ohlc",
    "synthetic_ohlcv",
    "midprice_ticks_to_ohlc",
    "ReplayBarSource",
    "try_import_replay_inprocess",
    "summarize_equity",
    "assert_fee_hurts_return",
    "EXPORT_API_VERSION",
    "export_batch",
    "export_single",
    "export_sma_signal",
    "export_sma_sweep",
    "research_manifest",
    "verify_export_golden",
    "golden_fixture",
    "verify_golden_vectors",
    "build_sma_cross_grid",
    "build_sma_cross_grid_numba_golden",
    "decide_research_accelerator",
    "plan_research_bytes",
]
