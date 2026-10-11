"""verify_strategy(events=...): the strategy sees events by publication time; the leaky join is priced; recheck."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify import recheck_certificate, verify_strategy

N = 900


@pytest.fixture(scope="module")
def market() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Daily bars; each event announces the sign of the next 5 days, published 5 days after the fact."""
    rng = np.random.default_rng(4)
    stamps = pd.date_range("2021-01-01", periods=N, freq="D")
    rets = rng.normal(0, 0.01, N)
    close = 100 * np.exp(np.cumsum(rets))
    op = np.r_[close[0], close[:-1]]
    df = pd.DataFrame({"timestamp": stamps, "open": op, "high": np.maximum(op, close) * 1.001,
                       "low": np.minimum(op, close) * 0.999, "close": close, "volume": 1e6})
    idx = np.arange(5, N - 6, 5)
    future = np.array([np.sign(close[i + 5] / close[i] - 1) for i in idx])
    events = pd.DataFrame({"event_time": stamps[idx], "published_at": stamps[idx] + pd.Timedelta(days=5), "surprise": future})
    return df, events


def strategy(df: pd.DataFrame) -> pd.Series:
    """Trade the latest known event value."""
    return df["ev_surprise"].fillna(0.0)


def test_events_joined_by_publication_and_leak_priced(market) -> None:
    df, events = market
    report = json.loads(json.dumps(verify_strategy(df, signal_fn=strategy, events=events, probe_checks=4)))
    rows = {c["id"]: c for c in report["checks"]}
    assert rows["events_quality"]["status"] in ("pass", "warn")
    pit = rows["pit_events"]
    assert pit["status"] == "warn", pit  # the event-time join knows the next 5 days
    assert pit["details"]["profit_event_time"] > pit["details"]["profit_published"]
    assert report["reproducibility"]["settings"]["events_delay"] == 0.0
    assert len(report["reproducibility"]["settings"]["events_sha256"]) == 64


def test_recheck_needs_the_same_events(market, tmp_path) -> None:
    df, events = market
    path = tmp_path / "events.csv"
    events.to_csv(path, index=False)
    script = tmp_path / "s.py"
    script.write_text("def signal(df):\n    return df['ev_surprise'].fillna(0.0)\n", encoding="utf-8")
    cert = json.loads(json.dumps(verify_strategy(df, strategy=str(script), events=str(path), probe_checks=4)))
    assert recheck_certificate(cert, df, strategy=str(script), events=str(path))["reproduced"]
    with pytest.raises(ValueError, match="events"):
        recheck_certificate(cert, df, strategy=str(script))
    other = events.assign(surprise=-events["surprise"])
    assert recheck_certificate(cert, df, strategy=str(script), events=other)["reproduced"] is False  # other inputs


def test_no_event_time_skips_the_comparison(market) -> None:
    df, events = market
    report = verify_strategy(df, signal_fn=strategy, events=events.drop(columns=["event_time"]), probe_checks=4)
    assert {c["id"]: c["status"] for c in report["checks"]}["pit_events"] == "skip"
