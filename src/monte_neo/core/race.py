"""Phase-2 race helpers: fused SMA sweep + Metal batch timing on Apple Silicon.

Private optimization surface for fair-race vs ManifoldBT CPU on M1.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd

try:
    from numba import njit, prange
except Exception:  # noqa: BLE001
    njit = None
    prange = range


def _sma(close: np.ndarray, window: int) -> np.ndarray:
    out = np.empty_like(close)
    out[:] = np.nan
    if window <= 0 or window > len(close):
        return out
    csum = np.cumsum(close)
    out[window - 1] = csum[window - 1] / window
    for i in range(window, len(close)):
        out[i] = (csum[i] - csum[i - window]) / window
    return out


if njit is not None:

    @njit(cache=True, parallel=True)
    def _batch_sma_pnl(close: np.ndarray, fast_arr: np.ndarray, slow_arr: np.ndarray) -> np.ndarray:
        n = close.shape[0]
        m = fast_arr.shape[0]
        rets = np.empty(m, dtype=np.float64)
        for j in prange(m):
            fast = int(fast_arr[j])
            slow = int(slow_arr[j])
            # rolling means
            fsum = 0.0
            ssum = 0.0
            pos = 0.0
            entry = 0.0
            equity = 1.0
            for i in range(n):
                fsum += close[i]
                ssum += close[i]
                if i >= fast:
                    fsum -= close[i - fast]
                if i >= slow:
                    ssum -= close[i - slow]
                if i + 1 < slow:
                    continue
                fma = fsum / fast
                sma = ssum / slow
                target = 1.0 if fma > sma else -1.0
                if target != pos and i + 1 < n:
                    if pos != 0.0:
                        equity *= 1.0 + pos * ((close[i] - entry) / entry)
                    entry = close[i]
                    pos = target
            if pos != 0.0:
                equity *= 1.0 + pos * ((close[n - 1] - entry) / entry)
            rets[j] = equity - 1.0
        return rets

else:

    def _batch_sma_pnl(close: np.ndarray, fast_arr: np.ndarray, slow_arr: np.ndarray) -> np.ndarray:
        m = fast_arr.shape[0]
        rets = np.empty(m, dtype=np.float64)
        for j in range(m):
            f = _sma(close, int(fast_arr[j]))
            s = _sma(close, int(slow_arr[j]))
            sig = np.where(np.isnan(f) | np.isnan(s), 0.0, np.where(f > s, 1.0, -1.0))
            pos = 0.0
            entry = 0.0
            equity = 1.0
            for i in range(1, len(close)):
                target = sig[i - 1]
                if target != pos:
                    if pos != 0.0:
                        equity *= 1.0 + pos * ((close[i] - entry) / entry)
                    if target != 0.0:
                        entry = close[i]
                        pos = target
                    else:
                        pos = 0.0
            rets[j] = equity - 1.0
        return rets


def fused_sma_sweep(data: pd.DataFrame, *, combos: int = 256) -> dict[str, Any]:
    """High-throughput SMA parameter sweep (Numba parallel on Apple Silicon CPU).

    Used by the comparison harness Phase 2. Precision: float64.
    """
    close = data["close"].to_numpy(dtype=np.float64, copy=True)
    pairs = [(f, s) for f in range(5, 21) for s in range(30, 51) if f < s][:combos]
    fast_arr = np.array([p[0] for p in pairs], dtype=np.int64)
    slow_arr = np.array([p[1] for p in pairs], dtype=np.int64)
    # Warmup compile
    _ = _batch_sma_pnl(close[: min(512, len(close))], fast_arr[:1], slow_arr[:1])
    t0 = time.perf_counter()
    rets = _batch_sma_pnl(close, fast_arr, slow_arr)
    elapsed = time.perf_counter() - t0
    return {
        "engine": "monte_neo",
        "device": "cpu_numba",
        "precision": "float64",
        "combos": len(pairs),
        "elapsed_s": elapsed,
        "best_return": float(np.max(rets)) if len(rets) else 0.0,
        "rows": [
            {"fast": int(fast_arr[i]), "slow": int(slow_arr[i]), "total_return": float(rets[i])}
            for i in range(len(pairs))
        ],
    }


def metal_scenario_batch(
    data: pd.DataFrame,
    *,
    n_scenarios: int = 1000,
    metal_driver: str = "auto",
    precision: str = "float32",
) -> dict[str, Any]:
    """Batch Monte Carlo / scenarios via MLX/Metal with optional CPU overlap prefetch."""
    from monte_neo.core.mlx_engine import MLXBacktestEngine
    from monte_neo.indicators.technical import RSIIndicator

    ind = RSIIndicator()
    ind.set_parameter("period", 14)
    engine = MLXBacktestEngine(precision=precision, metal_driver=metal_driver)
    # Best-effort async prefetch overlap (CPU prepare while GPU warms)
    try:
        import asyncio

        asyncio.get_event_loop().run_until_complete(engine.prefetch_data(data))
    except Exception:  # noqa: BLE001
        pass
    t0 = time.perf_counter()
    results, timing = engine.run_full_simulation(data, ind, n_scenarios=n_scenarios)
    elapsed = time.perf_counter() - t0
    n = len(results) if isinstance(results, list) else n_scenarios
    return {
        "engine": "monte_neo",
        "device": "metal",
        "precision": precision,
        "scenarios": n,
        "elapsed_s": elapsed,
        "timing": timing,
        "ok": True,
    }
