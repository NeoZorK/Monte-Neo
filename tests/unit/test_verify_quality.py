"""data_quality: spikes, frozen prices, split jumps, gaps in time and zero volume."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "traps"))
from trap_data import bad_tick_ohlcv, planted_momentum_ohlcv, universe_ohlcv  # noqa: E402

from monte_neo.backtest import synthetic_ohlcv  # noqa: E402
from monte_neo.verify import verify_strategy  # noqa: E402
from monte_neo.verify.checks import NEXT_ACTIONS  # noqa: E402
from monte_neo.verify.market import market_for  # noqa: E402
from monte_neo.verify.quality import (  # noqa: E402
    data_quality,
    frozen_bars,
    quality_row,
    spike_profit_share,
    spikes,
    split_jumps,
    time_gaps,
)


def _ohlc(close: np.ndarray) -> dict[str, np.ndarray]:
    close = np.asarray(close, dtype=np.float64)
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    return {"open": open_, "high": np.maximum(open_, close), "low": np.minimum(open_, close), "close": close}


def _walk(n: int = 2000, seed: int = 0, sigma: float = 0.005) -> np.ndarray:
    return 100.0 * np.exp(np.cumsum(np.random.default_rng(seed).normal(0.0, sigma, n)))


def _row(df: pd.DataFrame) -> dict:
    report = verify_strategy(df, signals=np.ones(len(df)))
    return next(c for c in report["checks"] if c["id"] == "data_quality")


def test_spike_found_and_real_jump_ignored() -> None:
    close = _walk()
    close[500] *= 1.2  # bad tick: the next bar undoes it
    close[1200:] *= 0.8  # real crash: it stays
    mask = spikes(close)
    assert mask.shape == (close.size, 1)
    assert np.flatnonzero(mask[:, 0]).tolist() == [500]


def test_spikes_on_short_and_nan_columns() -> None:
    assert not spikes(np.full(5, 100.0)).any()
    close = np.column_stack([_walk(300), np.r_[np.full(100, np.nan), _walk(200, seed=1)]])
    close[150, 1] *= 0.7
    assert np.argwhere(spikes(close)).tolist() == [[150, 1]]


def test_frozen_runs() -> None:
    c = np.array([1, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4], dtype=float)
    frozen = frozen_bars(_ohlc(c))[:, 0]
    assert frozen.astype(int).tolist() == [0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1]


def test_split_jump() -> None:
    close = _walk()
    close[800:] /= 2.0  # an unadjusted 2-for-1 split
    ohlc = _ohlc(close)
    found = split_jumps(ohlc)
    assert [(t, s) for t, s, _ in found] == [(800, 0)]
    assert found[0][2] == pytest.approx(0.5, abs=0.02)
    assert split_jumps(_ohlc(_walk())) == []
    # The open also after the split: the jump shows at the open and in the close, listed once.
    ohlc["open"][800] /= 2.0
    assert [(t, s) for t, s, _ in split_jumps(ohlc)] == [(800, 0)]


def _session(freq: str, per_day: int) -> pd.Series:
    days = pd.bdate_range("2021-01-01", "2022-12-31")
    days = days[~days.isin(pd.to_datetime(["2021-07-05", "2021-12-24", "2022-11-24"]))]
    stamps = [pd.date_range(d + pd.Timedelta("9h30min"), periods=per_day, freq=freq) for d in days]
    return pd.Series(np.concatenate([s.to_numpy() for s in stamps]))


@pytest.mark.parametrize(("freq", "per_day"), [("min", 390), ("5min", 78), ("h", 7)])
def test_session_nights_and_weekends_are_not_gaps(freq: str, per_day: int) -> None:
    assert time_gaps(_session(freq, per_day))["count"] == 0


def test_weekly_closed_market_and_daily_bars_are_not_gaps() -> None:
    fx = pd.date_range("2021-01-03 22:00", periods=30000, freq="h")
    closed = (fx.dayofweek == 5) | ((fx.dayofweek == 4) & (fx.hour >= 22)) | ((fx.dayofweek == 6) & (fx.hour < 22))
    assert time_gaps(pd.Series(fx[~closed]))["count"] == 0
    assert time_gaps(pd.Series(pd.bdate_range("2015-01-01", periods=2000)))["count"] == 0


def test_outages_are_gaps() -> None:
    hours = pd.date_range("2021-01-01", periods=20000, freq="h")
    gaps = time_gaps(pd.Series(hours.delete(range(5000, 5010)).delete(range(9000, 9100))))
    assert (gaps["count"], gaps["largest_hours"]) == (2, 101.0)
    minutes = pd.date_range("2021-01-01", periods=100000, freq="min").delete(range(1000, 1360))
    assert time_gaps(pd.Series(minutes))["count"] == 1
    # A missing week in a session market.
    session = _session("5min", 78)
    week = session[(session < "2022-03-07") | (session >= "2022-03-14")]
    assert time_gaps(week.reset_index(drop=True))["count"] == 1


def test_time_gaps_without_enough_time() -> None:
    empty = {"count": 0, "largest_hours": None, "missing_share": 0.0}
    assert time_gaps(None) == empty
    assert time_gaps(pd.Series(pd.date_range("2021", periods=10, freq="h"))) == empty
    assert time_gaps(pd.Series([pd.Timestamp("2021-01-01")] * 30)) == empty


def test_clean_data_passes() -> None:
    for df in (synthetic_ohlcv(3000, seed=1), planted_momentum_ohlcv(), universe_ohlcv()):
        market = market_for(df)
        q = data_quality(market.ohlc, market.timestamps, market.volume)
        row = quality_row(q, None, market.symbols)
        assert row["status"] == "pass", row["summary"]
        assert "spike_mask" not in row["details"]


@pytest.mark.parametrize("seed", range(4))
def test_fat_tails_are_not_spikes(seed: int) -> None:
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.standard_t(3, 5000) * 0.01))
    q = data_quality(_ohlc(close))
    assert q["spikes"] == 0 and q["split_jumps"] == 0


def test_findings_warn() -> None:
    close = _walk()
    close[300] *= 1.3
    close[1500:] *= 3.0
    close[900:960] = close[899]
    ohlc = _ohlc(close)
    stamps = pd.Series(pd.date_range("2021-01-01", periods=close.size + 50, freq="h").delete(range(1000, 1050)))
    volume = np.where(np.arange(close.size) % 5 == 0, 0.0, 10.0)
    row = quality_row(data_quality(ohlc, stamps, volume), None)
    assert row["status"] == "warn"
    for part in ("1 one-bar price spike", "of bars frozen", "1 split-like jump", "1 gap in time", "20% of bars without volume"):
        assert part in row["summary"], row["summary"]
    assert row["details"]["largest_gap_hours"] == pytest.approx(51.0)


def test_plural_findings_and_symbols() -> None:
    close = np.column_stack([_walk(), _walk(seed=1)])
    close[[300, 700], 1] *= 1.3
    close[1500:, 1] *= 2.0
    close[1800:, 1] /= 4.0
    q = data_quality(_ohlc_2d(close), None, np.array([np.nan]))
    row = quality_row(q, None, ["AAA", "BBB"])
    assert "2 one-bar price spikes" in row["summary"] and "2 split-like jumps" in row["summary"]
    assert {e["symbol"] for e in row["details"]["spike_examples"]} == {"BBB"}
    assert q["zero_volume_share"] is None


def _ohlc_2d(close: np.ndarray) -> dict[str, np.ndarray]:
    open_ = np.vstack([close[:1], close[:-1]])
    return {"open": open_, "high": np.maximum(open_, close), "low": np.minimum(open_, close), "close": close}


def test_spike_profit_share() -> None:
    mask = np.zeros(10, dtype=bool)
    mask[4] = True
    equity = np.array([1.0, 1.0, 1.01, 1.01, 1.01, 1.2, 1.2, 1.21, 1.21, 1.21])
    share = spike_profit_share(equity, mask)
    assert share == pytest.approx(np.log(1.2 / 1.01) / np.log(1.21))
    # Only spikes in held instruments count.
    assert spike_profit_share(equity, mask, traded=np.zeros(10)) is None
    held = np.zeros(10)
    held[5] = 1.0
    assert spike_profit_share(equity, mask, traded=held) == pytest.approx(share)
    assert spike_profit_share(equity, np.zeros(10, dtype=bool)) is None
    assert spike_profit_share(equity[::-1], mask) is None  # a loss has no profit share
    assert spike_profit_share(np.ones(2), mask[:2]) is None


def test_profit_from_spikes_fails_and_reports_action() -> None:
    report = verify_strategy(bad_tick_ohlcv(), strategy=Path(__file__).parents[1] / "traps" / "strategies" / "spike_fade.py")
    row = next(c for c in report["checks"] if c["id"] == "data_quality")
    assert row["status"] == "fail"
    assert row["details"]["spike_profit_share"] > 0.5
    assert report["verdict"] == "REJECT"
    assert NEXT_ACTIONS["data_quality"] in report["next_actions"]


def test_holding_through_spikes_only_warns() -> None:
    row = _row(bad_tick_ohlcv())
    assert row["status"] == "warn"
    assert row["details"]["spike_profit_share"] is None or row["details"]["spike_profit_share"] <= 0.5


def test_universe_volume_column_is_read() -> None:
    df = universe_ohlcv()
    df["volume"] = np.where(np.arange(len(df)) % 4 == 0, 0.0, 5.0)
    report = verify_strategy(df, signals=np.ones(len(df)))
    row = next(c for c in report["checks"] if c["id"] == "data_quality")
    assert row["details"]["zero_volume_share"] == pytest.approx(0.25, abs=0.01)
    assert row["status"] == "warn"
