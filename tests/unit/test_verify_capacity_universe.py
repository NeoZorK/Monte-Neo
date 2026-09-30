"""Capacity for universes: how much capital the fills of all symbols can absorb."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import ExecutionModel, synthetic_ohlcv
from monte_neo.verify import verify_strategy
from monte_neo.verify.microstructure import capacity, capacity_row
from monte_neo.verify.report_html import render_html

MODEL = ExecutionModel(warmup_bars=5)
NAMES = ("AAA", "BBB", "CCC")


def _flat_world(n: int = 60, m: int = 3):
    close = np.full((n, m), 100.0)
    volume = np.full((n, m), 1000.0)  # 100 000 traded per bar and symbol
    return close, volume


def test_a_single_symbol_order_is_capital_times_the_weight_change() -> None:
    close, volume = _flat_world()
    weights = np.zeros((60, 3))
    weights[10:, 0] = 0.5  # one order: symbol AAA from 0 to 0.5, decided at bar 9 (a change at 10 - 1)
    weights[30:, 0] = 0.0  # and back to 0
    info = capacity({"close": close}, volume, weights, MODEL, NAMES)
    assert info["fills"] == 2
    assert info["capital"] == [pytest.approx(2000.0), pytest.approx(10_000.0), pytest.approx(20_000.0)]  # 100 000 / 0.5 x share
    assert info["symbols"] == 3
    assert [r["symbol"] for r in info["by_symbol"]] == ["AAA"]  # only symbols that traded are listed


def test_the_tightest_symbol_sets_the_limit_and_leads_the_list() -> None:
    close, volume = _flat_world()
    volume[:, 1] = 100.0  # BBB trades 10 000 per bar: ten times thinner
    weights = np.zeros((60, 3))
    for k in range(3):
        weights[10:40, k] = 0.3
    info = capacity({"close": close}, volume, weights, MODEL, NAMES)
    order = [r["symbol"] for r in info["by_symbol"]]
    assert order[0] == "BBB" and set(order) == set(NAMES)
    tightest = info["by_symbol"][0]["capital"]
    # 6 fills in all; 90% of them inside the limit means the limit is set by the thin symbol's two fills.
    assert info["capital"][1] == pytest.approx(tightest[1], rel=0.25)
    assert tightest[1] == pytest.approx(0.05 * 10_000 / 0.3, abs=0.01)  # capital is rounded to cents


def test_size_fraction_and_leverage_scale_the_orders() -> None:
    close, volume = _flat_world()
    weights = np.zeros((60, 3))
    weights[10:, 0] = 1.0
    base = capacity({"close": close}, volume, weights, MODEL, NAMES)["capital"][1]
    half = capacity({"close": close}, volume, weights, ExecutionModel(warmup_bars=5, size_fraction=0.5), NAMES)["capital"][1]
    lever = capacity({"close": close}, volume, weights, ExecutionModel(warmup_bars=5, leverage=2.0), NAMES)["capital"][1]
    assert half == pytest.approx(2 * base) and lever == pytest.approx(base / 2)


def test_orders_before_the_warm_up_are_ignored_and_the_last_bar_still_fills() -> None:
    close, volume = _flat_world()
    weights = np.zeros((60, 3))
    weights[2:, 0] = 1.0  # decided inside the warm-up of 5 bars
    assert capacity({"close": close}, volume, weights, MODEL, NAMES) == {}
    late = np.zeros((60, 3))
    late[59, 0] = 1.0  # decided at bar 58, filled at the last bar: still a valid fill
    assert capacity({"close": close}, volume, late, MODEL, NAMES)["fills"] == 1


def test_missing_volume_is_counted_not_used() -> None:
    close, volume = _flat_world()
    volume[[10, 20], 0] = np.nan  # the fill bars of both AAA orders (decided at bars 9 and 19) have no volume
    weights = np.zeros((60, 3))
    weights[10:20, 0] = 0.5
    weights[10:20, 1] = 0.5
    info = capacity({"close": close}, volume, weights, MODEL, NAMES)
    assert info["fills_without_volume"] == 2 and info["fills"] == 2
    assert [r["symbol"] for r in info["by_symbol"]] == ["BBB"]
    assert capacity({"close": close}, np.full_like(volume, np.nan), weights, MODEL, NAMES) == {}


def test_symbols_are_optional_and_a_mismatch_is_ignored() -> None:
    close, volume = _flat_world()
    weights = np.zeros((60, 3))
    weights[10:, 0] = 0.5
    assert "by_symbol" not in capacity({"close": close}, volume, weights, MODEL)
    assert "by_symbol" not in capacity({"close": close}, volume, weights, MODEL, ("A", "B"))
    one = capacity({"close": close[:, :1]}, volume[:, :1], weights[:, :1], MODEL, ("A",))
    assert "by_symbol" not in one  # one column is a single instrument: no list


def test_the_row_names_the_tightest_symbols() -> None:
    close, volume = _flat_world()
    volume[:, 2] = 50.0
    weights = np.zeros((60, 3))
    for k in range(3):
        weights[10:30, k] = 0.3
    row = capacity_row(capacity({"close": close}, volume, weights, MODEL, NAMES))
    assert row["status"] == "info" and "tightest of 3 symbols at 5%: CCC" in row["summary"]


# ---- through the verifier and the report ------------------------------------------------------


def _universe(volume_scale: float | None = 1.0) -> pd.DataFrame:
    frames = []
    for k, sym in enumerate(NAMES):
        d = synthetic_ohlcv(500, seed=40 + k)
        d["timestamp"] = pd.date_range("2023-01-01", periods=500, freq="D")
        d["symbol"] = sym
        if volume_scale is None:
            d = d.drop(columns="volume")
        else:
            d["volume"] = d["volume"] * volume_scale * (0.1 if sym == "BBB" else 1.0)
        frames.append(d)
    return pd.concat(frames).sort_values(["timestamp", "symbol"]).reset_index(drop=True)


def _momentum(df: pd.DataFrame) -> pd.Series:
    mom = df.groupby("symbol")["close"].pct_change(10)
    return mom.groupby(df["timestamp"]).rank(pct=True).sub(0.5).fillna(0.0)


def test_a_universe_report_carries_capacity_rows_metric_and_table() -> None:
    report = verify_strategy(_universe(), signal_fn=_momentum)
    row = next(c for c in report["checks"] if c["id"] == "capacity")
    assert row["status"] == "info" and row["details"]["symbols"] == 3
    assert row["details"]["by_symbol"][0]["symbol"] == "BBB"  # the thinly traded symbol limits the strategy
    assert report["metrics"]["capacity_5pct"] == row["details"]["capital"][1] > 0
    page = render_html(report)
    assert "Capacity by symbol" in page and "BBB" in page and "capacity at 5% of volume" in page
    for bad in ("None", "NaN", "undefined"):
        assert bad not in page


def test_more_volume_means_more_capacity() -> None:
    small = verify_strategy(_universe(1.0), signal_fn=_momentum)["metrics"]["capacity_5pct"]
    large = verify_strategy(_universe(10.0), signal_fn=_momentum)["metrics"]["capacity_5pct"]
    assert large == pytest.approx(10 * small, rel=1e-6)


def test_no_volume_column_means_no_row_and_the_certificate_id_ignores_the_context_row() -> None:
    without = verify_strategy(_universe(None), signal_fn=_momentum)
    assert "capacity" not in {c["id"] for c in without["checks"]} and without["metrics"]["capacity_5pct"] is None
    # The capacity is context: the same data and code with a different volume column keeps the verdict.
    assert without["verdict"] == verify_strategy(_universe(1.0), signal_fn=_momentum)["verdict"]


def test_the_renderer_survives_a_malformed_capacity_check() -> None:
    report = verify_strategy(_universe(), signal_fn=_momentum)
    for check in report["checks"]:
        if check["id"] == "capacity":
            check["details"]["by_symbol"] = [None, "x", {"symbol": "Z", "capital": "oops"}, {"symbol": "Y", "capital": [1, "a", None], "fills": None}]
    page = render_html(report)
    assert "Capacity by symbol" in page


def test_a_single_instrument_run_is_unchanged() -> None:
    df = synthetic_ohlcv(1500, seed=2)
    sig = (df["close"] > df["close"].rolling(20).mean()).astype(int).to_numpy()
    report = verify_strategy(df, signals=sig)
    details = next(c for c in report["checks"] if c["id"] == "capacity")["details"]
    assert "by_symbol" not in details and "Capacity by symbol" not in render_html(report)
