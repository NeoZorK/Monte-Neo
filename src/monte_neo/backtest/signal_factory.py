"""Fast signal-grid factory for research sweeps (Numba parallel + optional MLX).

Builds (n_combos, n_bars) int64 long/flat signals. Numba float64 is the golden
reference; MLX float32 is best-effort on Apple Silicon and parity-tested with atol.
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
from numba import njit, prange

DeviceName = Literal["auto", "cpu_numba", "mlx"]


@njit(cache=True)
def _sma_cross_one(close: np.ndarray, fast: int, slow: int) -> np.ndarray:
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


@njit(parallel=True, cache=True)
def _sma_cross_grid_numba(
    close: np.ndarray, fasts: np.ndarray, slows: np.ndarray
) -> np.ndarray:
    n_bars = close.shape[0]
    n_combos = fasts.shape[0]
    out = np.zeros((n_combos, n_bars), dtype=np.int64)
    for i in prange(n_combos):
        out[i] = _sma_cross_one(close, int(fasts[i]), int(slows[i]))
    return out


def _sma_cross_grid_mlx(
    close: np.ndarray, fasts: np.ndarray, slows: np.ndarray
) -> np.ndarray:
    """MLX-accelerated SMA cross grid (float32). Falls back to Numba on error."""
    import mlx.core as mx

    c_np = np.asarray(close, dtype=np.float32)
    n = c_np.shape[0]
    c = mx.array(c_np)
    cs = mx.cumsum(c)
    mx.eval(cs)
    cs_np = np.array(cs)

    def _sma(period: int) -> np.ndarray:
        out = np.zeros(n, dtype=np.float64)
        if period <= 0 or period > n:
            return out
        for i in range(period - 1, n):
            prev = float(cs_np[i - period]) if i >= period else 0.0
            out[i] = (float(cs_np[i]) - prev) / float(period)
        return out

    periods = sorted({int(x) for x in list(fasts) + list(slows)})
    cache = {p: _sma(p) for p in periods}
    rows = []
    for f, s in zip(fasts.tolist(), slows.tolist(), strict=True):
        f_a = cache[int(f)]
        s_a = cache[int(s)]
        row = np.zeros(n, dtype=np.int64)
        start = int(s) - 1
        if start < 0:
            start = 0
        for i in range(start, n):
            row[i] = 1 if f_a[i] > s_a[i] else 0
        rows.append(row)
    return np.stack(rows, axis=0)


def build_sma_cross_grid(
    close: np.ndarray,
    pairs: list[tuple[int, int]] | np.ndarray,
    *,
    device: DeviceName = "auto",
) -> dict[str, Any]:
    """Build SMA cross long/flat signal grid.

    Returns dict with ``signals`` (n_combos, n_bars) int64, ``device``, ``elapsed_s``.
    """
    import time

    c = np.asarray(close, dtype=np.float64).reshape(-1)
    if isinstance(pairs, np.ndarray):
        if pairs.ndim != 2 or pairs.shape[1] != 2:
            raise ValueError("pairs ndarray must be (n, 2)")
        pair_list = [(int(a), int(b)) for a, b in pairs]
    else:
        pair_list = [(int(a), int(b)) for a, b in pairs]
    if not pair_list:
        raise ValueError("pairs must be non-empty")
    fasts = np.array([p[0] for p in pair_list], dtype=np.int64)
    slows = np.array([p[1] for p in pair_list], dtype=np.int64)

    want = device
    if want == "auto":
        # Numba parallel is the default fast+exact path; MLX is opt-in (float32).
        want = "cpu_numba"

    t0 = time.perf_counter()
    used = "cpu_numba"
    if want == "mlx":
        try:
            signals = _sma_cross_grid_mlx(c, fasts, slows)
            used = "mlx"
        except Exception:
            signals = _sma_cross_grid_numba(c, fasts, slows)
            used = "cpu_numba"
    else:
        signals = _sma_cross_grid_numba(c, fasts, slows)
        used = "cpu_numba"
    elapsed = time.perf_counter() - t0
    return {
        "signals": signals,
        "device": used,
        "elapsed_s": float(elapsed),
        "combos": int(signals.shape[0]),
        "bars": int(signals.shape[1]),
        "kind": "sma_cross",
    }


def build_sma_cross_grid_numba_golden(
    close: np.ndarray, pairs: list[tuple[int, int]]
) -> np.ndarray:
    """Always-Numba reference grid (parity / CI)."""
    c = np.asarray(close, dtype=np.float64).reshape(-1)
    fasts = np.array([int(a) for a, _ in pairs], dtype=np.int64)
    slows = np.array([int(b) for _, b in pairs], dtype=np.int64)
    return _sma_cross_grid_numba(c, fasts, slows)


__all__ = [
    "build_sma_cross_grid",
    "build_sma_cross_grid_numba_golden",
]
