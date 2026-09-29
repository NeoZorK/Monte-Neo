"""Numba JIT with an on-disk cache that degrades gracefully.

``njit(cache=True)`` raises at import time when Numba finds no writable directory for
its cache (read-only containers, a user without a home directory). The engines then
compile in memory on each run instead of failing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from numba import njit


def njit_cached(fn: Callable[..., Any]) -> Any:
    """``njit(cache=True)``, or plain ``njit`` when no cache location is writable."""
    try:
        return njit(cache=True)(fn)
    except RuntimeError:
        return njit(fn)


__all__ = ["njit_cached"]
