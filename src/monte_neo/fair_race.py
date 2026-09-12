"""Public fair-race helpers for ClaimBound / independent reproduce.

Type C: fused SMA sweep (Numba). Type B: Metal/MLX scenario batch.
Type A return-path MC peer lives in ClaimBound runner (shared returns vector).
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.core.race import fused_sma_sweep, metal_scenario_batch


def synthetic_ohlcv(n_bars: int = 50_000, seed: int = 42) -> pd.DataFrame:
    """Deterministic synthetic OHLCV for fair-race protocols."""
    rng = np.random.default_rng(seed + n_bars)
    dt = 1.0 / (60 * 24 * 365)
    mu, sigma = 0.05, 0.6
    rets = rng.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt), size=n_bars)
    close = 50_000.0 * np.exp(np.cumsum(rets))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    wiggle = rng.uniform(0.0001, 0.002, size=n_bars)
    high = np.maximum(open_, close) * (1.0 + wiggle)
    low = np.minimum(open_, close) * (1.0 - wiggle)
    volume = rng.uniform(1.0, 100.0, size=n_bars)
    ts = pd.date_range("2024-01-01", periods=n_bars, freq="min", tz="UTC")
    return pd.DataFrame(
        {"timestamp": ts, "open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )


def return_path_bootstrap(
    returns: np.ndarray,
    *,
    n_simulations: int = 1000,
    seed: int = 7,
) -> dict[str, Any]:
    """Type A peer: bootstrap equity paths from a fixed return vector (float64)."""
    r = np.asarray(returns, dtype=np.float64)
    if r.size == 0:
        raise ValueError("empty returns")
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    idx = rng.integers(0, r.size, size=(n_simulations, r.size))
    paths = np.cumprod(1.0 + r[idx], axis=1)
    elapsed = time.perf_counter() - t0
    terminal = paths[:, -1] - 1.0
    peak = np.maximum.accumulate(paths, axis=1)
    dd = (peak - paths) / np.maximum(peak, 1e-12)
    max_dd = dd.max(axis=1)
    return {
        "engine": "monte_neo",
        "device": "cpu",
        "method": "bootstrap",
        "n_simulations": n_simulations,
        "elapsed_s": elapsed,
        "sims_per_s": n_simulations / elapsed if elapsed > 0 else float("inf"),
        "terminal_p05": float(np.percentile(terminal, 5)),
        "terminal_p50": float(np.percentile(terminal, 50)),
        "terminal_p95": float(np.percentile(terminal, 95)),
        "max_dd_p50": float(np.percentile(max_dd, 50)),
        "ok": True,
    }


def run_type_c_sweep(n_bars: int = 50_000, combos: int = 256, seed: int = 42) -> dict[str, Any]:
    data = synthetic_ohlcv(n_bars, seed=seed)
    out = fused_sma_sweep(data, combos=combos)
    out["type"] = "C_sweep"
    out["bars"] = n_bars
    out["ok"] = True
    return out


def run_type_b_scenarios(
    n_bars: int = 50_000,
    n_scenarios: int = 1000,
    seed: int = 42,
    metal_driver: str = "auto",
) -> dict[str, Any]:
    data = synthetic_ohlcv(n_bars, seed=seed)
    try:
        out = metal_scenario_batch(
            data, n_scenarios=n_scenarios, metal_driver=metal_driver, precision="float32"
        )
        if out.get("ok", True) and out.get("elapsed_s"):
            out["type"] = "B_scenario_rebacktest"
            out["bars"] = n_bars
            out["scenarios_per_s"] = n_scenarios / float(out["elapsed_s"])
            out["ok"] = True
            return out
    except Exception as exc:  # noqa: BLE001
        metal_error = str(exc)
    else:
        metal_error = out.get("error", "metal path unavailable")

    # CPU fallback: repeat Numba fused single-grid eval as scenario proxy
    t0 = time.perf_counter()
    reps = min(n_scenarios, 200)
    for i in range(reps):
        fused_sma_sweep(data, combos=8)
    elapsed = time.perf_counter() - t0
    rate = reps / elapsed if elapsed > 0 else 0.0
    return {
        "type": "B_scenario_rebacktest",
        "ok": True,
        "engine": "monte_neo",
        "device": "cpu_fallback",
        "scenarios": n_scenarios,
        "timed_reps": reps,
        "elapsed_s_for_reps": elapsed,
        "scenarios_per_s": rate,
        "metal_error": metal_error,
        "note": "Metal unavailable; CPU fallback timed fused mini-sweeps as scenario proxy.",
    }
