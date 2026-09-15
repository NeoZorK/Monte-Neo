"""Strategy expression helpers → signal arrays for the shared ExecutionModel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numba import njit

StrategyKind = Literal["sma_cross", "ema_cross", "raw"]


@dataclass(frozen=True, slots=True)
class StrategySpec:
    """Declarative strategy that compiles to an int64 signal series."""

    kind: StrategyKind = "sma_cross"
    fast: int = 10
    slow: int = 40


@njit(cache=True)
def sma_signal_long_flat(close: np.ndarray, fast: int, slow: int) -> np.ndarray:  # pragma: no cover  # njit body; covered via public API / subprocess
    n = close.shape[0]
    out = np.zeros(n, dtype=np.int64)
    if fast <= 0 or slow <= fast or slow > n:
        return out
    fsum = 0.0
    ssum = 0.0
    for i in range(n):
        fsum += close[i]
        ssum += close[i]
        if i >= fast:
            fsum -= close[i - fast]
        if i >= slow:
            ssum -= close[i - slow]
        if i + 1 < slow:
            continue
        out[i] = 1 if (fsum / fast) > (ssum / slow) else 0
    return out


@njit(cache=True)
def _ema_signal_long_flat(close: np.ndarray, fast: int, slow: int) -> np.ndarray:  # pragma: no cover  # njit body; covered via public API / subprocess
    n = close.shape[0]
    out = np.zeros(n, dtype=np.int64)
    if fast <= 0 or slow <= fast or n == 0:
        return out
    a_f = 2.0 / (fast + 1)
    a_s = 2.0 / (slow + 1)
    ema_f = close[0]
    ema_s = close[0]
    for i in range(n):
        ema_f = a_f * close[i] + (1.0 - a_f) * ema_f
        ema_s = a_s * close[i] + (1.0 - a_s) * ema_s
        if i + 1 < slow:
            continue
        out[i] = 1 if ema_f > ema_s else 0
    return out


def build_signal(close: np.ndarray, spec: StrategySpec) -> np.ndarray:
    """Compile a :class:`StrategySpec` into a long/flat int64 signal."""
    c = np.asarray(close, dtype=np.float64)
    if spec.kind == "sma_cross":
        return sma_signal_long_flat(c, int(spec.fast), int(spec.slow))
    if spec.kind == "ema_cross":
        return _ema_signal_long_flat(c, int(spec.fast), int(spec.slow))
    if spec.kind == "raw":
        raise ValueError("raw kind requires an external signal array")
    raise ValueError(f"unknown strategy kind: {spec.kind}")
