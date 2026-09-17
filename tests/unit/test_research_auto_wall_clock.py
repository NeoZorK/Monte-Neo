"""Research device=auto prefers cpu_numba for wall clock (v0.17.5)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from monte_neo.backtest.memory_plan import (
    decide_research_accelerator,
    research_auto_should_attempt_accelerator,
)


@pytest.fixture(autouse=True)
def _clear_auto_metal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MONTE_NEO_RESEARCH_AUTO_PREFER_METAL", raising=False)
    monkeypatch.delenv("MONTE_NEO_RESEARCH_AUTO_METAL_MIN_COMBOS", raising=False)


def test_auto_declines_metal_for_typical_grids() -> None:
    with patch("monte_neo.oms.accel.device.resolve_device", return_value="metal"):
        d = decide_research_accelerator(n_bars=100_000, n_combos=64, device="auto")
    assert d["use_metal"] is False
    assert d["fallback_reason"] == "auto_prefer_cpu_numba"
    assert d["requested_device"] == "auto"
    assert d["want_device"] == "metal"


def test_auto_declines_metal_for_1m_grid() -> None:
    with patch("monte_neo.oms.accel.device.resolve_device", return_value="metal"):
        d = decide_research_accelerator(n_bars=1_000_000, n_combos=32, device="auto")
    assert d["use_metal"] is False
    assert d["fallback_reason"] == "auto_prefer_cpu_numba"


def test_explicit_metal_attempts_when_size_ok() -> None:
    with patch("monte_neo.oms.accel.device.resolve_device", return_value="metal"):
        d = decide_research_accelerator(n_bars=100_000, n_combos=64, device="metal")
    assert d["use_metal"] is True
    assert d["fallback_reason"] is None
    assert d["requested_device"] == "metal"


def test_explicit_mlx_attempts_when_size_ok() -> None:
    with patch("monte_neo.oms.accel.device.resolve_device", return_value="mlx"):
        d = decide_research_accelerator(n_bars=100_000, n_combos=64, device="mlx")
    assert d["use_mlx"] is True
    assert d["fallback_reason"] is None


def test_auto_mlx_also_prefers_cpu_numba() -> None:
    with patch("monte_neo.oms.accel.device.resolve_device", return_value="mlx"):
        d = decide_research_accelerator(n_bars=100_000, n_combos=64, device="auto")
    assert d["use_mlx"] is False
    assert d["fallback_reason"] == "auto_prefer_cpu_numba"


def test_env_prefer_metal_restores_old_auto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MONTE_NEO_RESEARCH_AUTO_PREFER_METAL", "1")
    assert research_auto_should_attempt_accelerator(n_combos=16) is True
    with patch("monte_neo.oms.accel.device.resolve_device", return_value="metal"):
        d = decide_research_accelerator(n_bars=50_000, n_combos=16, device="auto")
    assert d["use_metal"] is True
    assert d["fallback_reason"] is None


def test_env_min_combos_allows_wide_auto_metal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MONTE_NEO_RESEARCH_AUTO_METAL_MIN_COMBOS", "512")
    assert research_auto_should_attempt_accelerator(n_combos=64) is False
    assert research_auto_should_attempt_accelerator(n_combos=512) is True
    with patch("monte_neo.oms.accel.device.resolve_device", return_value="metal"):
        narrow = decide_research_accelerator(n_bars=50_000, n_combos=64, device="auto")
        wide = decide_research_accelerator(n_bars=50_000, n_combos=512, device="auto")
    assert narrow["use_metal"] is False
    assert narrow["fallback_reason"] == "auto_prefer_cpu_numba"
    assert wide["use_metal"] is True
    assert wide["fallback_reason"] is None


def test_size_gate_still_beats_wall_clock_policy() -> None:
    """Oversized Metal jobs still get metal_max_bars_exceeded, not auto_prefer."""
    with patch("monte_neo.oms.accel.device.resolve_device", return_value="metal"):
        d = decide_research_accelerator(
            n_bars=10_000_000, n_combos=16, device="auto"
        )
    assert d["use_metal"] is False
    assert d["fallback_reason"] == "metal_max_bars_exceeded"


def test_cpu_numba_request_unchanged() -> None:
    d = decide_research_accelerator(n_bars=100_000, n_combos=64, device="cpu_numba")
    assert d["use_metal"] is False
    assert d["fallback_reason"] is None
    assert d["want_device"] == "cpu_numba"
