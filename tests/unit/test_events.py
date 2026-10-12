"""Point-in-time events: load, join by publication time, quality and the PIT row."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify.events import join_events, load_events
from monte_neo.verify.events_checks import events_quality, events_quality_row, pit_events_row


def _bars(n: int = 10, symbols: tuple[str, ...] | None = None) -> pd.DataFrame:
    t = pd.date_range("2024-01-01", periods=n, freq="1D")
    px = 100.0 + np.arange(n)
    frame = pd.DataFrame({"timestamp": t, "open": px, "high": px + 1, "low": px - 1, "close": px + 0.5})
    if symbols is None:
        return frame
    parts = [frame.assign(symbol=s, open=frame["open"] + i) for i, s in enumerate(symbols)]
    return pd.concat(parts).sort_values(["timestamp", "symbol"]).reset_index(drop=True)


def _events(rows: list[tuple]) -> pd.DataFrame:
    return load_events(pd.DataFrame(rows, columns=["published_at", "event_time", "score"]))


def test_event_published_mid_bar_visible_next_bar() -> None:
    ev = _events([("2024-01-04 12:00", "2024-01-01", 1.5)])
    col = join_events(_bars(), ev)["ev_score"]
    assert col.iloc[:4].isna().all()  # bars Jan 1..4: Jan 4 opens before the publication
    assert (col.iloc[4:] == 1.5).all()  # usable from Jan 5


def test_event_at_exact_open_is_not_visible_on_that_bar() -> None:
    ev = _events([("2024-01-04 00:00", "2024-01-01", 2.0)])
    col = join_events(_bars(), ev)["ev_score"]
    assert np.isnan(col.iloc[3]) and col.iloc[4] == 2.0


def test_delay_shifts_visibility_and_latest_event_wins() -> None:
    ev = _events([("2024-01-03", "2024-01-01", 1.0), ("2024-01-06", "2024-01-05", 2.0)])
    base = join_events(_bars(), ev)["ev_score"]
    late = join_events(_bars(), ev, delay=pd.Timedelta(days=2))["ev_score"]
    assert base.iloc[3] == 1.0 and base.iloc[6] == 2.0
    assert np.isnan(late.iloc[3]) and late.iloc[5] == 1.0 and late.iloc[6] == 1.0 and late.iloc[8] == 2.0


def test_by_event_time_is_the_leaky_join() -> None:
    ev = _events([("2024-01-08", "2024-01-02", 3.0)])
    honest = join_events(_bars(), ev)["ev_score"]
    leaky = join_events(_bars(), ev, by="event_time")["ev_score"]
    assert honest.notna().sum() < leaky.notna().sum()
    assert leaky.iloc[2] == 3.0 and np.isnan(honest.iloc[2])


def test_universe_join_per_symbol_and_row_order() -> None:
    bars = _bars(6, ("AAA", "BBB"))
    ev = load_events(pd.DataFrame({"published_at": ["2024-01-02", "2024-01-04"], "symbol": ["AAA", "BBB"], "score": [1.0, 2.0]}))
    out = join_events(bars, ev)
    assert (out["timestamp"] == bars["timestamp"]).all() and (out["symbol"] == bars["symbol"]).all()
    aaa, bbb = out[out["symbol"] == "AAA"], out[out["symbol"] == "BBB"]
    assert np.isnan(aaa["ev_score"].iloc[1]) and aaa["ev_score"].iloc[2] == 1.0
    assert (aaa["ev_score"].dropna() == 1.0).all() and (bbb["ev_score"].dropna() == 2.0).all()
    assert bbb["ev_score"].isna().sum() == 4  # Jan 1..4 not yet visible


def test_universe_requires_symbol_in_events() -> None:
    with pytest.raises(ValueError, match="symbol"):
        join_events(_bars(4, ("A", "B")), _events([("2024-01-02", "2024-01-01", 1.0)]))


def test_shuffled_ohlcv_keeps_order() -> None:
    bars = _bars().sample(frac=1.0, random_state=1).reset_index(drop=True)
    ev = _events([("2024-01-04 12:00", "2024-01-01", 1.5)])
    out = join_events(bars, ev)
    assert (out["timestamp"] == bars["timestamp"]).all()
    assert (out.loc[out["timestamp"] >= "2024-01-05", "ev_score"] == 1.5).all()
    assert out.loc[out["timestamp"] < "2024-01-05", "ev_score"].isna().all()


def test_join_is_causal() -> None:
    bars = _bars(12)
    ev = _events([("2024-01-03", "2024-01-01", 1.0), ("2024-01-07 10:00", "2024-01-06", 2.0), ("2024-01-11", "2024-01-09", 3.0)])
    full = join_events(bars, ev)
    t = 7
    cut = join_events(bars.iloc[: t + 1], ev)
    pd.testing.assert_series_equal(full["ev_score"].iloc[: t + 1], cut["ev_score"], check_names=False)


def test_does_not_mutate_inputs() -> None:
    bars, ev = _bars(), _events([("2024-01-04", "2024-01-01", 1.0)])
    before = bars.copy()
    join_events(bars, ev)
    pd.testing.assert_frame_equal(bars, before)


def test_quality_published_before_event_warns() -> None:
    ev = _events([("2024-01-02", "2024-01-05", 1.0), ("2024-01-08", "2024-01-06", 1.0)])
    row = events_quality_row(ev, _bars())
    assert row["id"] == "events_quality" and row["category"] == "integrity" and row["status"] == "warn"
    assert row["details"]["published_before_event"] == 1 and "impossible" in row["summary"]


def test_quality_zero_delay_warns() -> None:
    ev = _events([("2024-01-02", "2024-01-02", 1.0), ("2024-01-05", "2024-01-05", 1.0)])
    row = events_quality_row(ev, _bars())
    assert row["status"] == "warn" and "copy of event_time" in row["summary"]
    assert row["details"]["same_bar_share"] == 1.0


def test_quality_good_delay_passes_and_stats() -> None:
    ev = _events([("2024-01-04", "2024-01-01", 1.0), ("2024-01-09", "2024-01-05", 1.0)])
    info = events_quality(ev, _bars())
    assert info["delay_median_s"] == pytest.approx(3.5 * 86400) and info["same_bar_share"] == 0.0
    assert events_quality_row(ev, _bars())["status"] == "pass"


def test_quality_outside_range_and_no_event_time() -> None:
    ev = load_events(pd.DataFrame({"published_at": ["2023-12-01", "2024-01-03"], "score": [1.0, 2.0]}))
    info = events_quality(ev, _bars())
    assert info["outside_range"] == 1 and info["no_event_time"] == 2
    assert "no event_time" in events_quality_row(ev, _bars())["summary"]


def test_pit_row_statuses() -> None:
    assert pit_events_row(0.10, None)["status"] == "skip"
    info = pit_events_row(0.10, 0.12)
    assert info["status"] == "info" and info["category"] == "lookahead"
    assert info["details"]["gap_pp"] == pytest.approx(2.0)
    assert pit_events_row(0.02, 0.30)["status"] == "warn"
    assert pit_events_row(0.04, 0.12)["status"] == "warn"
    assert pit_events_row(0.04, 0.07)["status"] == "info"  # gap 3 pp
    assert pit_events_row(0.10, 0.18)["status"] == "info"  # 8 pp but not 2x


def test_load_errors() -> None:
    with pytest.raises(ValueError, match="published_at"):
        load_events(pd.DataFrame({"event_time": ["2024-01-01"], "x": [1.0]}))
    with pytest.raises(ValueError, match="cannot parse"):
        load_events(pd.DataFrame({"published_at": ["not a date"], "x": [1.0]}))
    with pytest.raises(ValueError, match="no numeric value"):
        load_events(pd.DataFrame({"published_at": ["2024-01-01"], "event_time": ["2023-12-31"]}))
    with pytest.raises(ValueError, match="duplicate"):
        load_events(pd.DataFrame({"published_at": ["2024-01-01", "2024-01-01"], "x": [1.0, 2.0]}))
    with pytest.raises(ValueError, match="symbol"):
        load_events(pd.DataFrame({"published_at": ["2024-01-01"], "symbol": [None], "x": [1.0]}))


def test_load_from_csv_utc_to_naive(tmp_path: Path) -> None:
    path = tmp_path / "ev.csv"
    path.write_text("Published_At,Ticker,Score\n2024-01-01T10:00:00+02:00,AAA,1.5\n")
    ev = load_events(path)
    assert ev["published_at"].iloc[0] == pd.Timestamp("2024-01-01 08:00:00")
    assert ev["published_at"].dt.tz is None and ev["symbol"].iloc[0] == "AAA"
