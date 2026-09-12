"""Unit tests for public fair_race helpers."""

from __future__ import annotations

import numpy as np

from monte_neo.fair_race import return_path_bootstrap, run_type_c_sweep, synthetic_ohlcv


def test_synthetic_deterministic():
    a = synthetic_ohlcv(1000, seed=42)
    b = synthetic_ohlcv(1000, seed=42)
    assert np.allclose(a["close"], b["close"])


def test_type_c_sweep_small():
    out = run_type_c_sweep(n_bars=2000, combos=16, seed=42)
    assert out["ok"] is True
    assert out["combos"] == 16


def test_return_path_bootstrap():
    rets = np.diff(np.log(synthetic_ohlcv(500, seed=1)["close"].to_numpy()))
    out = return_path_bootstrap(rets, n_simulations=100, seed=7)
    assert out["ok"] is True
    assert out["n_simulations"] == 100
