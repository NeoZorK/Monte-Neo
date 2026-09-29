"""CLI interface module.

Attributes load on first access: ``monte-neo verify`` / ``bench`` / ``mcp`` must not
pay for the interactive research menu and its dependencies.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY = {
    "MonteNeoCLI": "monte_neo.cli.app",
    "main": "monte_neo.cli.app",
    "InteractiveMenu": "monte_neo.cli.menu",
    "ProgressTracker": "monte_neo.cli.progress",
}

__all__ = ["main", "MonteNeoCLI", "InteractiveMenu", "ProgressTracker"]


def __getattr__(name: str) -> Any:
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module 'monte_neo.cli' has no attribute {name!r}")
    return getattr(import_module(module), name)
