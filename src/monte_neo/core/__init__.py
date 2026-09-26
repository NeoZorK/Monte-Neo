"""Core generator module (lazy exports; see :mod:`monte_neo`)."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY = {
    "IndicatorGenerator": "monte_neo.core.generator",
    "ParameterOptimizer": "monte_neo.core.optimizer",
    "OverfitValidator": "monte_neo.core.validator",
}

__all__ = ["IndicatorGenerator", "ParameterOptimizer", "OverfitValidator"]


def __getattr__(name: str) -> Any:
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module 'monte_neo.core' has no attribute {name!r}")
    return getattr(import_module(module), name)
