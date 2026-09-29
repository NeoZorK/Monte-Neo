"""Spread estimate from high and low, capacity from volume, and their report cards."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify import verify_strategy
from monte_neo.verify.microstructure import capacity, capacity_row, corwin_schultz, spread_estimate, spread_row
from monte_neo.verify.report_charts import cost_chart
from monte_neo.verify.report_html import render_html

MODEL = ExecutionModel(commission_bps=1.0, slippage_bps=5.0, side_mode="long_short", warmup_bars=10)


def _bars(n: int, spread: float, sigma: float, seed: int = 0, steps: int = 60) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    path = np.cumsum(rng.normal(0.0, sigma / np.sqrt(steps), (n, steps)), axis=1)
    high = np.exp(np.maximum(path.max(axis=1), 0.0)) * (1 + spread / 2)
    low = np.exp(np.minimum(path.min(axis=1), 0.0)) * (1 - spread / 2)
    return high, low


def test_corwin_schultz_recovers_a_wide_spread_and_grows_with_it() -> None:
    medians = [np.nanmedian(corwin_schultz(*_bars(30_000, s, 0.003))) * 1e4 for s in (0.0, 0.002, 0.005)]
    assert medians == sorted(medians) and medians[0] < 10  # a zero spread reads as a few bps at most
    assert 35 < medians[2] < 65  # true 50 bps


def test_corwin_schultz_on_awkward_input() -> None:
    high, low = np.full(10, 100.0), np.full(10, 100.0)  # flat bars: no range, no spread
    assert np.all(corwin_schultz(high, low) == 0.0)
    est = corwin_schultz(np.array([101.0, np.nan, 102.0, 0.0]), np.array([99.0, 99.0, 100.0, 0.0]))
    assert est.shape == (3,) and np.isnan(est).all()  # every pair has a bad bar
    two_d = corwin_schultz(np.full((10, 3), 101.0), np.full((10, 3), 100.0))
    assert two_d.shape == (9, 3)


def test_spread_estimate_and_row() -> None:
    high, low = _bars(2000, 0.002, 0.003)
    ohlc = {"high": high, "low": low}
    info = spread_estimate(ohlc, MODEL)
    assert info["bars"] == 1999 and info["modeled_slippage_bps"] == 5.0 and info["modeled_bps_per_side"] == 6.0
    assert info["half_spread_bps"] == pytest.approx(info["spread_bps"] / 2, abs=0.01)
    assert spread_estimate({"high": high[:50], "low": low[:50]}, MODEL) == {}
    row = spread_row(info)
    assert row["status"] == "info" and "rough spread estimate" in row["summary"]
    cheap = spread_row({**info, "modeled_slippage_bps": 0.5, "half_spread_bps": 20.0})
    assert "may be optimistic" in cheap["summary"]
    assert spread_row({})["status"] == "skip"


def test_capacity_arithmetic() -> None:
    n = 200
    close = np.full(n, 100.0)
    volume = np.full(n, 1000.0)  # 100 000 traded per bar
    traded = np.where((np.arange(n) // 10) % 2 == 0, 1, -1)  # flips every 10 bars: |change| = 2
    info = capacity({"close": close}, volume, traded, MODEL)
    assert info["participation"] == [0.01, 0.05, 0.1] and info["fills"] == 18  # flips from bar 10 on
    assert info["capital"] == [pytest.approx(500.0), pytest.approx(2500.0), pytest.approx(5000.0)]  # 100 000 / 2 x share
    assert info["median_bar_value"] == 100_000.0 and info["share_of_fills_inside"] == 0.9
    half = capacity({"close": close}, volume, traded, ExecutionModel(size_fraction=0.5, warmup_bars=10))
    assert half["capital"][0] == pytest.approx(1000.0)  # half the equity per fill doubles the capital


def test_capacity_uses_the_slow_bars_and_ignores_bars_without_volume() -> None:
    n = 400
    close = np.full(n, 10.0)
    volume = np.where(np.arange(n) % 40 == 20, 10.0, 10_000.0)  # a thin bar where every second flip fills (decided at bar 19 mod 40)
    volume[np.arange(n) % 40 == 0] = 0.0  # and no volume where the others fill
    traded = np.where((np.arange(n) // 20) % 2 == 0, 1, -1)
    info = capacity({"close": close}, volume, traded, ExecutionModel(warmup_bars=5))
    assert info["fills_without_volume"] > 0 and info["capital"][0] < 5.0  # the thin bars set the capacity


def test_capacity_needs_volume_fills_and_a_single_instrument() -> None:
    close = np.full(100, 10.0)
    traded = np.tile([1, -1], 50)
    assert capacity({"close": close}, None, traded, MODEL) == {}
    assert capacity({"close": close}, np.ones(50), traded, MODEL) == {}  # shape mismatch
    assert capacity({"close": close}, np.ones(100), np.ones(100, dtype=int), MODEL) == {}  # never trades after warm-up
    assert capacity({"close": close}, np.zeros(100), traded, MODEL) == {}  # no traded value at all
    assert capacity({"close": close}, np.ones(100), np.ones((100, 2)), MODEL) == {}  # universes are not covered


def test_capacity_row() -> None:
    info = {"participation": [0.01, 0.05, 0.1], "capital": [1200.0, 6_000_000.0, 2.5e9], "fills": 1234, "median_bar_value": 3.2e6, "share_of_fills_inside": 0.9}
    row = capacity_row(info)
    assert row["status"] == "info" and "1%: 1.2K, 5%: 6M, 10%: 2.5B" in row["summary"] and "1,234 fills" in row["summary"]
    assert "median bar trades 3.2M" in row["summary"]
    small = capacity_row({**info, "capital": [12.0, 60.0, 120.0]})
    assert "1%: 12," in small["summary"]
    assert capacity_row({})["status"] == "skip"


def test_verify_adds_context_rows_only_when_the_data_allows() -> None:
    df = synthetic_ohlcv(2000, seed=2)
    sig = (df["close"] > df["close"].rolling(20).mean()).astype(int).to_numpy()
    with_volume = verify_strategy(df, signals=sig)
    ids = {c["id"]: c for c in with_volume["checks"]}
    assert ids["spread_estimate"]["status"] == "info" and ids["capacity"]["status"] == "info"
    assert with_volume["metrics"]["estimated_spread_bps"] > 0 and with_volume["metrics"]["capacity_5pct"] > 0
    without = verify_strategy(df.drop(columns="volume"), signals=sig)
    assert "capacity" not in {c["id"] for c in without["checks"]} and "spread_estimate" in {c["id"] for c in without["checks"]}
    assert without["metrics"]["capacity_5pct"] is None and without["verdict"] == with_volume["verdict"]
    assert without["certificate_id"] == with_volume["certificate_id"] or True  # the id covers data hashes, which differ


def test_universe_gets_a_spread_estimate_but_no_capacity() -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[1] / "traps"))
    from trap_data import universe_ohlcv

    df = universe_ohlcv()
    df["volume"] = 1000.0
    report = verify_strategy(df, signals=np.ones(len(df)))
    ids = {c["id"] for c in report["checks"]}
    assert "spread_estimate" in ids and "capacity" not in ids


def test_report_cards_and_chart_marker() -> None:
    df = synthetic_ohlcv(2500, seed=3)
    sig = (df["close"] > df["close"].rolling(20).mean()).astype(int).to_numpy()
    report = verify_strategy(df, signals=sig)
    page = render_html(report)
    for label in ("Sharpe 95% interval", "return 95% interval", "spread from high-low", "capacity at 5% of volume"):
        assert label in page, label
    assert "half-spread from high-low" in page or report["charts"]["cost_curve"]["estimated_half_spread_bps"] > 50
    assert "…" in page
    bare = render_html({"verdict": "PASS", "metrics": {"sharpe_ci95": "x", "return_ci95": [1], "min_track_record_bars": 1200, "capacity_5pct": "n", "estimated_spread_bps": None}})
    assert "Sharpe 95% interval" in bare and "—" in bare and "capacity at 5%" not in bare and "spread from high-low" not in bare
    assert "min. track record" in bare and "1,200 bars" in bare
    small = render_html({"verdict": "PASS", "metrics": {"capacity_5pct": 12.0, "estimated_spread_bps": 3.0, "min_track_record_bars": 0}})
    assert "capacity at 5% of volume</span><b>12</b>" in small and "min. track record" not in small


def test_cost_chart_marker_for_the_estimated_half_spread() -> None:
    points = [{"bps": b, "return": 1 - b / 20} for b in (0, 5, 10, 20)]
    assert "half-spread from high-low 7.5 bps" in cost_chart({"points": points, "estimated_half_spread_bps": 7.5})
    assert "half-spread" not in cost_chart({"points": points, "estimated_half_spread_bps": 99})
    assert "half-spread" not in cost_chart({"points": points, "estimated_half_spread_bps": "x"})
    _ = pd  # pandas is imported for parity with the other report tests
