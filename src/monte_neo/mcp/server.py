"""``monte-neo-mcp`` — stdio / HTTP MCP server exposing the strategy verifier.

Works with the MCP Python SDK 2.x (``MCPServer``) and 1.x (``FastMCP``).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from monte_neo._version import __version__
from monte_neo.mcp.tools import SERVER_INSTRUCTIONS, TOOLS

SERVER_NAME = "monte-neo"


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


def build_server() -> Any:
    """Create the MCP server with every verifier tool registered."""
    cls = _server_class()
    server = cls(name=SERVER_NAME, instructions=SERVER_INSTRUCTIONS)
    for fn in TOOLS:
        server.tool()(fn)
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
