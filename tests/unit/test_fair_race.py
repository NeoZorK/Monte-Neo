"""Unit tests for public fair-race helpers."""

from __future__ import annotations

from monte_neo import __version__
from monte_neo.fair_race import (
    return_path_bootstrap,
    run_type_b_scenarios,
    run_type_c_sweep,
    synthetic_ohlcv,
)


def test_package_version_matches_source() -> None:
    assert __version__.startswith("v0.0.")


def test_synthetic_ohlcv_shape_and_seed() -> None:
    a = synthetic_ohlcv(n_bars=1_000, seed=42)
    b = synthetic_ohlcv(n_bars=1_000, seed=42)
    assert list(a.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(a) == 1_000
    assert a["close"].equals(b["close"])


def test_type_c_sweep_throughput_ok() -> None:
    out = run_type_c_sweep(n_bars=5_000, combos=16, seed=42)
    assert out["ok"] is True
    assert out["combos"] == 16
    assert out["combos_per_s"] > 0


def test_type_a_bootstrap_ok() -> None:
    data = synthetic_ohlcv(n_bars=2_000, seed=42)
    import numpy as np

    rets = np.diff(np.log(data["close"].to_numpy()))
    out = return_path_bootstrap(rets, n_simulations=32, seed=7)
    assert out["ok"] is True
    assert out["sims_per_s"] > 0


def test_type_b_scenarios_ok_with_cpu_fallback() -> None:
    out = run_type_b_scenarios(n_bars=2_000, n_scenarios=8, seed=42)
    assert out["ok"] is True
    assert out["scenarios_per_s"] > 0
    assert out.get("device") in {"metal", "cpu_fallback", "cpu_numba", "cpu"}
