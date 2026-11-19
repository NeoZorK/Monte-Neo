"""A candidate is strategy code plus parameters; its id is a hash of both, so a renamed copy is the same variant."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

from monte_neo.verify.ledger import variant_id


def canonical_params(params: dict[str, Any] | None) -> str:
    return json.dumps(params or {}, sort_keys=True, separators=(",", ":"), default=str)


def frozen_source(source: str, params: dict[str, Any] | None) -> str:
    """The code with its parameters written into it as a statement, so the code hash covers the parameters."""
    return source.rstrip() + f"\n__PARAMS__ = {canonical_params(params)!r}\n"


@dataclass(frozen=True)
class Candidate:
    """``signal(df, **params)`` source text, the parameters and a label."""

    source: str
    params: dict[str, Any] = field(default_factory=dict)
    label: str = ""

    @property
    def id(self) -> str:
        code = variant_id(self.source) or "src:none"
        return code.split(":", 1)[0] + ":" + hashlib.sha256((code + "|" + canonical_params(self.params)).encode()).hexdigest()[:16]

    @classmethod
    def from_file(cls, path: str | Path, params: dict[str, Any] | None = None, label: str = "") -> Candidate:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"strategy file not found: {p}")
        return cls(p.read_text(encoding="utf-8"), dict(params or {}), label or p.stem)

    @classmethod
    def from_callable(cls, fn: Callable[..., Any], params: dict[str, Any] | None = None, label: str = "") -> Candidate:
        import textwrap

        try:
            src = textwrap.dedent(inspect.getsource(fn))
        except (OSError, TypeError) as exc:
            raise ValueError("cannot read the source of this callable; use Candidate(source, params)") from exc
        name = getattr(fn, "__name__", "signal")
        if name != "signal":
            src = src.replace(f"def {name}(", "def signal(", 1)
        return cls("import numpy as np\nimport pandas as pd\n\n" + src, dict(params or {}), label or name)

    def signal_fn(self) -> Callable[..., Any]:
        """Run the code and return ``partial(signal, **params)``. Runs the code with your permissions: only your own code."""
        ns: dict[str, Any] = {"__name__": "_research_candidate"}
        exec(compile(self.source, f"<candidate {self.id}>", "exec"), ns)  # noqa: S102
        fn = ns.get("signal")
        if not callable(fn):
            raise ValueError("the candidate code must define signal(df, **params)")
        return partial(fn, **self.params)


__all__ = ["Candidate", "canonical_params", "frozen_source"]
