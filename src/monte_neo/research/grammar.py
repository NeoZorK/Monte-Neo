"""Signal grammar as a plugin: a Python file that says which variants of a strategy to screen.

A grammar file defines the strategy and the variants; it runs with your permissions, so use only your own files::

    SOURCE = '''
    import numpy as np
    def signal(df, n=20):
        ...
    '''                       # or STRATEGY = "strategy.py" (a path next to the grammar file)
    GRID = {"n": [10, 20, 40]}          # expanded as a Cartesian product, or:
    def variants():                     # any iterable of parameter dicts (a generator is fine)
        for n in range(5, 200, 5):
            yield {"n": n}
    LABEL = "sma"                       # optional

Every variant is one candidate (code hash and parameters). The grammar file is hashed into the project manifest, so a changed grammar is
visible; a grammar that yields more than ``MAX_VARIANTS`` variants is refused (the search cost grows with every one).
"""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from monte_neo.research.candidate import Candidate

MAX_VARIANTS = 5000

DEMO_SOURCE = '''import numpy as np


def signal(df, fast=10, slow=40):
    """Trend rule: long when the fast average is above the slow one, short otherwise."""
    c = df["close"].to_numpy()

    def sma(n):
        out = np.full(len(c), np.nan)
        cs = np.cumsum(np.insert(c, 0, 0.0))
        out[n - 1:] = (cs[n:] - cs[:-n]) / n
        return out

    f, s = sma(fast), sma(slow)
    pos = np.where(f > s, 1, -1)
    pos[np.isnan(s)] = 0
    return pos
'''
DEMO_GRID = {"fast": [5, 10, 20, 30], "slow": [40, 60, 90, 120]}


@dataclass
class Grammar:
    """The variants a grammar file yields."""

    source: str
    label: str
    _variants: list[dict[str, Any]]
    sha256: str
    path: str | None = None

    def __len__(self) -> int:
        return len(self._variants)

    def candidates(self) -> Iterator[Candidate]:
        for params in self._variants:
            yield Candidate(self.source, dict(params), f"{self.label} {_label(params)}")

    def manifest_entry(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "variants": len(self), "label": self.label}


def expand_grid(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Cartesian product of ``{name: [values]}`` (no cap here: :data:`MAX_VARIANTS` is checked on the result)."""
    if not grid or any(isinstance(v, str | bytes) or not hasattr(v, "__iter__") or not list(v) for v in grid.values()):
        raise ValueError("GRID must be a dict of non-empty lists, for example {\"n\": [10, 20]}")
    names = sorted(grid)
    return [dict(zip(names, combo, strict=True)) for combo in itertools.product(*(list(grid[k]) for k in names))]


def _label(params: dict[str, Any]) -> str:
    return ",".join(f"{k}={params[k]}" for k in sorted(params))


def demo_grammar() -> Grammar:
    """The built-in grammar of the dry run: a trend rule with a 4 x 4 grid of averages."""
    variants = [v for v in expand_grid(DEMO_GRID) if v["fast"] < v["slow"]]
    sha = hashlib.sha256((DEMO_SOURCE + repr(sorted(DEMO_GRID.items()))).encode()).hexdigest()
    return Grammar(DEMO_SOURCE, "demo-trend", variants, sha)


def load_grammar(path: str | Path) -> Grammar:
    """Run a grammar file and collect its variants.

    Raises:
        ValueError: No ``SOURCE`` or ``STRATEGY``, no ``GRID`` or ``variants()``, no variants, or more than :data:`MAX_VARIANTS`.
        FileNotFoundError: The file or the strategy it names does not exist.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"grammar file not found: {p}")
    text = p.read_text(encoding="utf-8")
    name = f"_research_grammar_{hashlib.sha256(str(p.resolve()).encode()).hexdigest()[:10]}"
    spec = importlib.util.spec_from_file_location(name, p)
    if spec is None or spec.loader is None:  # pragma: no cover - importlib edge
        raise ImportError(f"cannot import {p}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    if hasattr(mod, "SOURCE"):
        source = str(mod.SOURCE)
    elif hasattr(mod, "STRATEGY"):
        strat = p.parent / str(mod.STRATEGY)
        if not strat.is_file():
            raise FileNotFoundError(f"the strategy file named by the grammar was not found: {strat}")
        source = strat.read_text(encoding="utf-8")
    else:
        raise ValueError("the grammar file must define SOURCE (the strategy text) or STRATEGY (a file next to it)")
    if hasattr(mod, "variants"):
        variants = [dict(v) for v in itertools.islice(mod.variants(), MAX_VARIANTS + 1)]
    elif hasattr(mod, "GRID"):
        variants = expand_grid(mod.GRID)
    else:
        raise ValueError("the grammar file must define GRID (a dict of lists) or variants() (an iterable of parameter dicts)")
    if not variants:
        raise ValueError("the grammar yields no variants")
    if len(variants) > MAX_VARIANTS:
        raise ValueError(f"the grammar yields more than {MAX_VARIANTS} variants: every one is a trial that the search has to pay for; narrow it")
    sha = hashlib.sha256((text + source).encode()).hexdigest()
    return Grammar(source, str(getattr(mod, "LABEL", p.stem)), variants, sha, str(p.resolve()))


__all__ = ["DEMO_GRID", "DEMO_SOURCE", "MAX_VARIANTS", "Grammar", "demo_grammar", "load_grammar"]
