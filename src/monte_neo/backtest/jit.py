"""Numba JIT that degrades gracefully.

The engines are written as plain loops and compiled with Numba when it is installed. Two
things can be missing, and neither stops the verifier:

* **Numba itself** (PyPy, WebAssembly, a Python version without Numba wheels, ``--no-deps``
  installs): the same source runs as ordinary Python. The numbers are identical bit for bit;
  only the speed differs (about 100x slower for one backtest, see ``docs/api/verify.md``).
  ``prange`` becomes ``range``. Nothing is downloaded: ``pip install "monte-neo[fast]"``
  adds Numba.
* **A writable cache directory** for compiled code (read-only containers, no home
  directory): the engines compile in memory instead of failing at import.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any

try:
    import numba
except ImportError:  # pragma: no cover - runs in the subprocess test without Numba
    numba = None  # PyPy, WebAssembly, unsupported Python, --no-deps

HAS_NUMBA = numba is not None
SLOW_BARS = 20_000
SLOW_HINT = (
    "Numba is not installed: backtests run as plain Python, about 100x slower for {bars:,} bars "
    "(results are identical). For speed: pip install 'monte-neo[fast]'"
)
prange = numba.prange if HAS_NUMBA else range


def njit(*args: Any, **kwargs: Any) -> Any:
    """``numba.njit`` (any call form), or the plain function without Numba."""
    bare = len(args) == 1 and callable(args[0]) and not kwargs
    if not HAS_NUMBA:
        return args[0] if bare else (lambda fn: fn)
    if bare:
        return numba.njit(args[0])

    def wrap(fn: Callable[..., Any]) -> Any:
        try:
            return numba.njit(*args, **kwargs)(fn)
        except RuntimeError:
            if not kwargs.get("cache"):
                raise
            # No writable cache location: compile in memory.
            return numba.njit(*args, **{**kwargs, "cache": False})(fn)

    return wrap


def njit_cached(fn: Callable[..., Any]) -> Any:
    """``njit(cache=True)``."""
    return njit(cache=True)(fn)


def warn_if_slow(bars: int) -> None:
    """Tell the user once that a large run uses the plain-Python engine."""
    if not HAS_NUMBA and bars >= SLOW_BARS:
        warnings.warn(SLOW_HINT.format(bars=bars), RuntimeWarning, stacklevel=3)


__all__ = ["HAS_NUMBA", "SLOW_BARS", "SLOW_HINT", "njit", "njit_cached", "prange", "warn_if_slow"]
