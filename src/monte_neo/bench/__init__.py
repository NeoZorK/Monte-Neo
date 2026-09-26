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

__all__ = [
    "BENCH_SCHEMA_ID",
    "load_bench",
    "render_markdown",
    "run_bench",
    "score_submission",
    "summarize_agents",
]
