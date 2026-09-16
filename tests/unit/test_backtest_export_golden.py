"""Export API + golden vectors for honest external harnesses."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.backtest import (
    EXPORT_API_VERSION,
    ExecutionModel,
    export_batch,
    export_single,
    export_sma_signal,
    export_sma_sweep,
    golden_fixture,
    research_manifest,
    verify_export_golden,
    verify_golden_vectors,
)


def test_research_manifest_stable_keys() -> None:
    m = research_manifest()
    assert m["export_api_version"] == EXPORT_API_VERSION
    assert m["lane"] == "research_bar"
    assert "next_bar_fill" in m["required_work_keys"]
    assert "export_single" in m["entrypoints"]


def test_golden_vectors_numba_exact() -> None:
    report = verify_golden_vectors(device="cpu_numba")
    assert report["ok"] is True
    assert all(report["checks"].values())


def test_verify_export_golden_wraps() -> None:
    report = verify_export_golden(device="cpu_numba")
    assert report["ok"] is True
    assert report["export_api_version"] == EXPORT_API_VERSION
    assert report["lane"] == "research_bar"


def test_export_single_schema_and_fee_hurts() -> None:
    fx = golden_fixture()
    ohlc = fx["ohlc"]
    sig = fx["signal"]
    z = export_single(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=fx["model_zero_fee"]
    )
    f = export_single(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=fx["model_fee"]
    )
    for out in (z, f):
        assert out["ok"] is True
        assert out["export_api_version"] == EXPORT_API_VERSION
        assert out["timing"]["includes_signal_build"] is False
        assert out["work_checklist"]["next_bar_fill"] is True
        assert out["work_checklist"]["cash_position_equity"] is True
        assert "total_return" in out["metrics"]
    assert f["metrics"]["total_return"] <= z["metrics"]["total_return"] + 1e-12
    assert f["work_checklist"]["fees"] is True
    assert f["work_checklist"]["slippage"] is True


def test_export_batch_matches_single_pair() -> None:
    fx = golden_fixture()
    ohlc = fx["ohlc"]
    sigs = np.stack(
        [export_sma_signal(ohlc["close"], a, b) for a, b in fx["batch_smas"]]
    )
    model = fx["model_fee"]
    batch = export_batch(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        sigs,
        model=model,
        device="cpu_numba",
    )
    single = export_single(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        sigs[2],
        model=model,
    )
    assert batch["ok"] is True
    assert batch["timing"]["includes_signal_build"] is False
    assert batch["combos"] == 3
    assert np.isclose(
        float(batch["metrics"]["total_returns"][2]),
        float(single["metrics"]["total_return"]),
        rtol=1e-12,
        atol=1e-14,
    )


def test_export_sma_sweep_discloses_signal_build() -> None:
    fx = golden_fixture()
    ohlc = fx["ohlc"]
    model = ExecutionModel(
        commission_bps=5.0,
        slippage_bps=5.0,
        warmup_bars=40,
        size_fraction=0.5,
        side_mode="long_flat",
    )
    out = export_sma_sweep(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        combos=8,
        model=model,
        device="cpu_numba",
    )
    assert out["ok"] is True
    assert out["timing"]["includes_signal_build"] is True
    assert out["combos"] == 8
    assert out["work_checklist"]["next_bar_fill"] is True


def test_verify_export_golden_metal_uses_float32_band() -> None:
    """Metal float32 batch must pass with auto-widened tolerances."""
    from monte_neo.oms.accel.device import metal_available

    if not metal_available():
        pytest.skip("Metal unavailable")
    report = verify_export_golden(device="metal")
    assert report["ok"] is True
    assert report.get("device") == "metal"
    assert report.get("atol") == pytest.approx(1e-5)
    assert report["checks"]["batch_returns"] is True
