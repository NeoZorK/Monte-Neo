"""Monte-Neo: strategy verifier and fee-aware research engine.

Heavy submodules (generator, Monte Carlo, optional MLX/Metal backends) are
imported lazily on first attribute access, so ``import monte_neo`` and
``import monte_neo.verify`` never load native GPU libraries.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from monte_neo._version import __version__

_LAZY = {
    "IndicatorGenerator": "monte_neo.core.generator",
    "MetricsCalculator": "monte_neo.metrics.calculator",
    "MonteCarloEngine": "monte_neo.monte_carlo.engine",
}

__all__ = ["__version__", "IndicatorGenerator", "MonteCarloEngine", "MetricsCalculator"]


def __getattr__(name: str) -> Any:
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module 'monte_neo' has no attribute {name!r}")
    return getattr(import_module(module), name)
