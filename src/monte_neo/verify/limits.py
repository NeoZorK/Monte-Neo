"""Input limits and strict parsing: bounded memory and no ambiguous JSON.

The verifier reads files chosen by users and by AI agents (which may act on injected
instructions), so every input has a size limit with a clear error. Limits are generous
for real use; ``MONTE_NEO_MAX_INPUT_MB`` raises the one for price tables.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

MB = 1024 * 1024
DEFAULT_TABLE_MB = 2048
MAX_CERTIFICATE_BYTES = 64 * MB
MAX_SOURCE_BYTES = 5 * MB
MAX_KEY_BYTES = 4096
MAX_GRID_BYTES = MB
MAX_JSON_DEPTH = 100


def table_limit_bytes() -> int:
    """Largest OHLCV / signals file in bytes (``MONTE_NEO_MAX_INPUT_MB``, default 2048)."""
    raw = os.environ.get("MONTE_NEO_MAX_INPUT_MB", "")
    try:
        return int(float(raw) * MB) if raw else DEFAULT_TABLE_MB * MB
    except ValueError:
        return DEFAULT_TABLE_MB * MB


def check_size(path: str | Path, limit: int, what: str) -> Path:
    """Raise a clear error when ``path`` is larger than ``limit`` bytes."""
    p = Path(path)
    size = p.stat().st_size
    if size > limit:
        hint = " Set MONTE_NEO_MAX_INPUT_MB to raise the limit." if what == "table" else ""
        raise ValueError(f"{what} file {p.name} is {size / MB:.3g} MB, over the {limit / MB:.3g} MB limit.{hint}")
    return p


def read_text_limited(path: str | Path, limit: int, what: str) -> str:
    """UTF-8 text of a file no larger than ``limit`` bytes."""
    return check_size(path, limit, what).read_text(encoding="utf-8")


def read_source(path: str | Path) -> str:
    """Source of a strategy file (limited to 5 MB)."""
    return read_text_limited(path, MAX_SOURCE_BYTES, "strategy")


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate key {key!r} in JSON object")
        out[key] = value
    return out


def _no_constants(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON")


def _too_deep(value: Any, limit: int) -> bool:
    """True when containers nest deeper than ``limit`` (iterative: no recursion limit to hit)."""
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        children = item.values() if isinstance(item, dict) else item if isinstance(item, list) else ()
        for child in children:
            if isinstance(child, dict | list):
                if depth + 1 > limit:
                    return True
                stack.append((child, depth + 1))
    return False


def loads_strict(text: str) -> Any:
    """``json.loads`` that rejects duplicate keys, NaN / Infinity and nesting over 100 levels.

    The browser verification page applies the same rules, so a file means the same everywhere.
    """
    try:
        value = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_no_constants)
    except RecursionError as exc:
        raise ValueError("JSON is nested too deeply") from exc
    if _too_deep(value, MAX_JSON_DEPTH):
        raise ValueError("JSON is nested too deeply")
    return value


__all__ = [
    "MAX_CERTIFICATE_BYTES",
    "MAX_GRID_BYTES",
    "MAX_KEY_BYTES",
    "MAX_SOURCE_BYTES",
    "check_size",
    "loads_strict",
    "read_source",
    "read_text_limited",
    "table_limit_bytes",
]
