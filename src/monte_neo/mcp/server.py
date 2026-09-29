"""``monte-neo-mcp`` — stdio / HTTP MCP server exposing the strategy verifier.

Works with the MCP Python SDK 2.x (``MCPServer``) and 1.x (``FastMCP``).
"""

from __future__ import annotations

import argparse
import functools
import sys
from collections.abc import Callable
from typing import Any

from monte_neo._version import __version__
from monte_neo.mcp.tools import SERVER_INSTRUCTIONS, TOOLS

SERVER_NAME = "monte-neo"
WEBSITE_URL = "https://neozork.github.io/Monte-Neo/"


def _server_class() -> Any:
    try:
        from mcp.server.mcpserver import MCPServer  # SDK 2.x

        return MCPServer
    except ImportError:
        pass
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[attr-defined]  # SDK 1.x

        return FastMCP
    except ImportError as exc:
        raise SystemExit('MCP SDK missing: pip install "monte-neo[mcp]"') from exc


def reporting_errors(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """Return input errors to the agent as ``{"error": ...}`` instead of a bare tool failure.

    The SDK answers an exception with "Error executing tool <name>" and drops the reason,
    so an agent cannot tell a wrong path from a broken strategy. ``functools.wraps`` keeps
    the signature and annotations the SDK builds the tool schema from.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}", "tool": fn.__name__}

    return wrapper


def build_server() -> Any:
    """Create the MCP server with every verifier tool registered."""
    cls = _server_class()
    try:
        # SDK 2.x reports version and website to clients during initialize.
        server = cls(
            name=SERVER_NAME,
            instructions=SERVER_INSTRUCTIONS,
            version=__version__.lstrip("v"),
            website_url=WEBSITE_URL,
        )
    except TypeError:  # SDK 1.x FastMCP has no version / website_url arguments
        server = cls(name=SERVER_NAME, instructions=SERVER_INSTRUCTIONS)
    for fn in TOOLS:
        server.tool()(reporting_errors(fn))
    return server


def main(argv: list[str] | None = None) -> int:
    """Run the server (stdio by default)."""
    parser = argparse.ArgumentParser(prog="monte-neo-mcp", description="Monte-Neo strategy verifier MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--version", action="version", version=f"monte-neo-mcp {__version__}")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    build_server().run(transport=args.transport)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
