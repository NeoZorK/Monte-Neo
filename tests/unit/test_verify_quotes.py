"""quotes: loading, quote quality, and bars on the exchange and arrival clocks."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify.checks import NEXT_ACTIONS
from monte_neo.verify.quotes import (
    STALE_MS,
    bars_from_quotes,
    load_quotes,
    make_grid,
    quote_quality,
    quote_row,
    synthetic_quotes,
)
from monte_neo.verify.schema import CATEGORIES


def _table(n: int = 6, **over: object) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "timestamp": pd.Timestamp("2025-10-02", tz="UTC") + pd.to_timedelta(np.arange(n) * 100, unit="ms"),
            "bid_price": 99.0 + np.arange(n),
            "ask_price": 101.0 + np.arange(n),
            "latency": [5.0, 30.0, 5.0, 300.0, 5.0, 5.0][:n],
            "ticker": [("AAA-USDT@BINANCE", "AAA-USDT@KRAKEN")[i % 2] for i in range(n)],
        }
    )
    for key, value in over.items():
        frame[key] = value
    return frame


def test_load_maps_the_sample_dataset_column_names() -> None:
    q = load_quotes(_table())
    assert len(q) == 6
    assert q.mid[0] == 100.0
    assert q.venue is not None and set(q.venue) == {"BINANCE", "KRAKEN"}


def test_load_takes_an_arrival_column_and_a_venue_column() -> None:
    df = _table().drop(columns=["latency", "ticker"])
    df["arrival"] = pd.to_datetime(df["timestamp"]) + pd.to_timedelta([5, 30, 5, 300, 5, 5], unit="ms")
    df["venue"] = "X"
    q = load_quotes(df)
    assert q.latency_ms.tolist() == pytest.approx([5, 30, 5, 300, 5, 5])
    assert set(q.venue) == {"X"}


def test_load_without_venue_and_sorted_by_exchange_time() -> None:
    df = _table().drop(columns=["ticker"]).iloc[::-1].reset_index(drop=True)
    q = load_quotes(df)
    assert q.venue is None
    assert np.all(np.diff(q.exchange_ns) > 0)


def test_load_names_what_is_missing() -> None:
    with pytest.raises(ValueError, match="quotes need columns"):
        load_quotes(_table().drop(columns=["bid_price"]))
    with pytest.raises(ValueError, match="latency_ms"):
        load_quotes(_table().drop(columns=["latency"]))
    with pytest.raises(ValueError, match="no usable quote rows"):
        load_quotes(_table(timestamp="not a time"))


def test_load_drops_rows_that_do_not_parse() -> None:
    q = load_quotes(_table(bid_price=["x", 1.0, 2.0, 3.0, 4.0, 5.0]))
    assert len(q) == 5 and q.dropped == 1


def test_quality_of_clean_quotes_reports_the_latency_profile() -> None:
    info = quote_quality(load_quotes(_table()))
    assert info["status"] == "pass"
    assert info["latency_ms"]["p50"] == 5.0
    assert info["stale_ms"] == STALE_MS
    assert info["share_stale"] == pytest.approx(2 / 6)
    assert info["out_of_order_arrivals"] == 2  # the 405 and 505 ms arrivals overtake the 300 ms quote stamped before them
    assert set(info["latency_p50_ms_by_venue"]) == {"BINANCE", "KRAKEN"}
    row = quote_row(info)
    assert row["id"] == "quote_quality" and row["status"] == "pass" and "p95" in row["summary"]


def test_quality_warns_on_crossed_negative_and_bad_prices() -> None:
    df = _table(bid_price=[101.5, 100.0, 101.0, 102.0, 103.0, 104.0], latency=[-1.0, 5, 5, 5, 5, 5]).drop(columns=["ticker"])
    info = quote_quality(load_quotes(df))
    assert info["crossed"] >= 1 and info["negative_latency"] == 1 and info["status"] == "warn"
    assert info["locked"] == 0 and "latency_p50_ms_by_venue" not in info
    assert "crossed" in quote_row(info)["summary"]
    zero = quote_quality(load_quotes(_table(bid_price=[0.0, 99, 100, 101, 102, 103])))
    assert zero["non_positive_price"] == 1 and zero["status"] == "warn"


def test_row_ids_and_categories_are_registered() -> None:
    row = quote_row(quote_quality(load_quotes(_table())))
    assert row["category"] in CATEGORIES
    assert "quote_quality" in NEXT_ACTIONS


def test_grid_rejects_a_non_positive_bar_and_covers_the_arrival_clock() -> None:
    q = load_quotes(_table())
    with pytest.raises(ValueError, match="bar_ms"):
        make_grid(q, 0.0)
    plain, padded = make_grid(q, 100.0), make_grid(q, 100.0, max_extra_ms=1000.0)
    assert padded.n_bars > plain.n_bars >= 6


def test_bars_have_consistent_ohlc_and_count_every_quote() -> None:
    q = load_quotes(synthetic_quotes(3000))
    grid = make_grid(q, 50.0, max_extra_ms=100.0)
    for clock in ("exchange", "arrival"):
        bars = bars_from_quotes(q, grid, clock=clock)
        assert bars["close"].size == grid.n_bars
        assert bars["volume"].sum() == len(q)
        assert np.all(bars["high"] >= np.maximum(bars["open"], bars["close"]) - 1e-12)
        assert np.all(bars["low"] <= np.minimum(bars["open"], bars["close"]) + 1e-12)
        assert not np.isnan(bars["close"]).any()


def test_with_zero_latency_both_clocks_give_the_same_bars() -> None:
    q = load_quotes(synthetic_quotes(2000).assign(latency_ms=0.0))
    grid = make_grid(q, 50.0)
    a, b = bars_from_quotes(q, grid), bars_from_quotes(q, grid, clock="arrival")
    assert all(np.array_equal(a[k], b[k]) for k in a)


def test_latency_moves_quotes_into_later_bars_and_can_be_overridden() -> None:
    q = load_quotes(synthetic_quotes(2000))
    grid = make_grid(q, 20.0, max_extra_ms=500.0)
    now, later = bars_from_quotes(q, grid, clock="arrival"), bars_from_quotes(q, grid, clock="arrival", extra_latency_ms=500.0)
    assert not np.array_equal(now["close"], later["close"])
    forced = bars_from_quotes(q, grid, clock="arrival", latency_ms=np.zeros(len(q)))
    plain = bars_from_quotes(q, grid)
    assert np.array_equal(forced["close"], plain["close"])


def test_empty_bars_repeat_the_previous_close_with_zero_volume() -> None:
    q = load_quotes(_table(3).assign(latency=0.0))
    bars = bars_from_quotes(q, make_grid(q, 10.0))
    empty = bars["volume"] == 0
    assert empty.any()
    idx = np.flatnonzero(empty)[0]
    assert bars["open"][idx] == bars["high"][idx] == bars["low"][idx] == bars["close"][idx] == bars["close"][idx - 1]


def test_unknown_clock_is_rejected() -> None:
    q = load_quotes(_table())
    with pytest.raises(ValueError, match="clock"):
        bars_from_quotes(q, make_grid(q, 100.0), clock="wall")


def test_synthetic_quotes_are_reproducible_and_latency_is_bounded() -> None:
    a, b = synthetic_quotes(500, seed=3), synthetic_quotes(500, seed=3)
    assert a.equals(b)
    assert a["latency_ms"].between(5.0, 275.0).all()
    assert not synthetic_quotes(500, seed=4).equals(a)
    trending = synthetic_quotes(500, drift=1e-4)
    assert (trending["bid"] < trending["ask"]).all()
