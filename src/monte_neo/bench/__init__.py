"""Agent Backtest Honesty Bench: score agent-built strategies with the verifier."""

from __future__ import annotations

from monte_neo.bench.honesty import (
    BENCH_SCHEMA_ID,
    load_bench,
    render_markdown,
    run_bench,
    score_submission,
    summarize_agents,
)
from monte_neo.bench.tasks_v1 import BENCH_VERSION, TASKS, ar_ohlcv, init_bench

__all__ = [
    "BENCH_SCHEMA_ID",
    "BENCH_VERSION",
    "TASKS",
    "ar_ohlcv",
    "init_bench",
    "load_bench",
    "render_markdown",
    "run_bench",
    "score_submission",
    "summarize_agents",
]
