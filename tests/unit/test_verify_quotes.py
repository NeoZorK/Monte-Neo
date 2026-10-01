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
    select_symbol,
    synthetic_quotes,
)
from monte_neo.verify.schema import CATEGORIES


def _table(n: int = 6, **over: object) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "timestamp": pd.Timestamp("2025-10-02", tz="UTC") + pd.to_timedelta(np.arange(n) * 100, unit="ms"),
            "bid_price": 99.0 + np.arange(n),
            "ask_price": 101.0 + np.arange(n),
            "latency": ([5.0, 30.0, 5.0, 300.0, 5.0, 5.0] * (n // 6 + 1))[:n],
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


def test_bursty_latency_is_flagged_because_it_measures_the_path_not_the_exchange() -> None:
    calm = _table(60, latency=np.full(60, 20.0))
    assert quote_quality(load_quotes(calm))["bursty_latency"] is False
    stalled = _table(100, latency=np.r_[np.full(94, 20.0), np.full(6, 5000.0)])
    info = quote_quality(load_quotes(stalled.drop(columns=["ticker"])))
    assert info["bursty_latency"] is True and info["latency_p99_over_p50"] > 20 and info["status"] == "warn"
    summary = quote_row(info)["summary"]
    assert "queue up" in summary and "measure your network" in summary
    zero = quote_quality(load_quotes(_table(20, latency=np.zeros(20))))
    assert zero["latency_p99_over_p50"] is None and zero["bursty_latency"] is False


def _two_symbols() -> pd.DataFrame:
    a, b = synthetic_quotes(30, seed=1), synthetic_quotes(10, seed=2)
    a["symbol"], b["symbol"] = "AAA-USDT@X", "BBB-USDT@X"
    return pd.concat([a, b], ignore_index=True)


def test_select_symbol_needs_a_choice_when_there_are_several_and_names_the_options() -> None:
    q = load_quotes(_two_symbols())
    with pytest.raises(ValueError, match=r"2 symbols: pass symbol=.*AAA-USDT@X \(30\)"):
        select_symbol(q)
    one = select_symbol(q, "BBB-USDT@X")
    assert len(one) == 10 and set(one.symbol) == {"BBB-USDT@X"} and np.all(np.diff(one.exchange_ns) >= 0)
    with pytest.raises(ValueError, match="not in the quotes"):
        select_symbol(q, "ZZZ")


def test_select_symbol_with_one_symbol_or_none_at_all() -> None:
    single = load_quotes(synthetic_quotes(20))
    assert select_symbol(single) is single and select_symbol(single, "SYN-USDT@SIM") is not single
    bare = load_quotes(synthetic_quotes(20).drop(columns=["symbol"]))
    assert select_symbol(bare) is bare
    with pytest.raises(ValueError, match="no symbol column"):
        select_symbol(bare, "AAA")


def test_order_latency_moves_the_market_bars_later_in_time() -> None:
    q = load_quotes(synthetic_quotes(2000))
    grid = make_grid(q, 50.0)
    now = bars_from_quotes(q, grid)
    later = bars_from_quotes(q, grid, order_latency_ms=200.0)
    shifted = np.r_[now["close"][4:], np.full(4, now["close"][-1])]  # 200 ms = four 50 ms bars
    assert not np.array_equal(now["close"], later["close"])
    assert np.corrcoef(later["close"][:-8], shifted[:-8])[0, 1] > 0.999
    assert np.array_equal(bars_from_quotes(q, grid, order_latency_ms=0.0)["close"], now["close"])
