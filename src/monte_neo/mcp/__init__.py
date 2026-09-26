"""MCP (Model Context Protocol) adapter for the Monte-Neo strategy verifier.

Install with ``pip install "monte-neo[mcp]"`` and run ``monte-neo-mcp`` (stdio).
Tool logic lives in :mod:`monte_neo.mcp.tools` and has no MCP dependency.
"""

from __future__ import annotations

from monte_neo.mcp.tools import (
    SERVER_INSTRUCTIONS,
    TOOLS,
    cost_stress,
    probe_lookahead,
    verdict_schema,
    verifier_manifest,
    verify_grid,
    verify_strategy,
)

__all__ = [
    "SERVER_INSTRUCTIONS",
    "TOOLS",
    "cost_stress",
    "probe_lookahead",
    "verdict_schema",
    "verifier_manifest",
    "verify_grid",
    "verify_strategy",
]
