"""Parity / smoke tests for Metal vs Numba OMS batch."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.oms.accel.compute_pref import preferred_compute_device
from monte_neo.oms.accel.device import metal_available
from monte_neo.oms.accel.match_numba import batch_terminal_long_flat
from monte_neo.oms.accel.metal_dispatch import get_metal_oms_engine, run_batch_terminal


def _toy_case() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = 256
    open_ = np.linspace(100.0, 110.0, n)
    close = open_.copy()
    sig = np.zeros((8, n), dtype=np.int64)
    sig[:, 40:200] = 1
    return open_, close, sig


def test_preferred_compute_device_shape() -> None:
    info = preferred_compute_device("cpu_numba")
    assert info["resolved"] == "cpu_numba"
    assert "checklist" in info


def test_run_batch_terminal_cpu() -> None:
    open_, close, sig = _toy_case()
    out = run_batch_terminal(
        open_, close, sig, commission_bps=5.0, slip_bps=5.0, device="cpu_numba"
    )
    assert out["ok"] is True
    assert out["device_used"] == "cpu_numba"
    assert out["returns"].shape == (8,)


@pytest.mark.skipif(get_metal_oms_engine() is None, reason="Metal OMS engine unavailable")
def test_metal_batch_parity_vs_numba() -> None:
    eng = get_metal_oms_engine()
    assert eng is not None
    open_, close, sig = _toy_case()
    cpu = batch_terminal_long_flat(
        open_.astype(np.float64),
        close.astype(np.float64),
        sig,
        5.0,
        5.0,
        100_000.0,
        1.0,
        0,
    )
    metal = eng.batch_terminal_long_flat(
        open_, close, sig, 5.0, 5.0, 100_000.0, 1.0, 0
    )
    # float32 Metal vs float64 Numba: allow small relative tolerance
    assert np.allclose(cpu, metal, rtol=1e-4, atol=1e-5)


def test_run_batch_terminal_auto_reports_device() -> None:
    open_, close, sig = _toy_case()
    out = run_batch_terminal(open_, close, sig, device="auto")
    assert out["device_used"] in {"metal", "cpu_numba", "mlx"}
    assert out["returns"].shape[0] == 8
