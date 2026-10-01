"""quote_recorder: parsing, clock offset, CSV, and a recording with a fake connection."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from monte_neo.data import quote_recorder as rec
from monte_neo.verify.quotes import load_quotes, quote_quality


def _msg(event_ms: int, bid: str = "100.0", ask: str = "100.1", symbol: str = "BTCUSDT") -> str:
    return json.dumps({"e": "bookTicker", "u": 1, "s": symbol, "b": bid, "B": "1", "a": ask, "A": "2", "T": event_ms, "E": event_ms})


class FakeConnection:
    def __init__(self, messages: list[str]) -> None:
        self.messages, self.closed = list(messages), False

    def recv(self) -> str:
        return self.messages.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeClock:
    """Each call advances 1 ms of local time, so receive times are predictable."""

    def __init__(self, start_ns: int) -> None:
        self.now = start_ns

    def __call__(self) -> int:
        self.now += 1_000_000
        return self.now


def test_parse_accepts_plain_and_combined_frames_and_rejects_the_rest() -> None:
    plain = rec.parse_book_ticker(_msg(1_000))
    assert plain == {"event_ms": 1000, "bid": 100.0, "ask": 100.1, "symbol": "BTCUSDT"}
    combined = rec.parse_book_ticker(json.dumps({"stream": "x", "data": json.loads(_msg(2_000))}))
    assert combined is not None and combined["event_ms"] == 2000
    assert rec.parse_book_ticker(_msg(1, bid="nan")) is None
    for junk in ("not json", "[]", '{"e": "trade"}', '{"e": "bookTicker"}', '{"e": "bookTicker", "b": "x", "a": "1", "E": 1, "s": "A"}', None):
        assert rec.parse_book_ticker(junk) is None  # type: ignore[arg-type]
    assert rec.parse_book_ticker(json.loads(_msg(5)))["event_ms"] == 5  # type: ignore[index]


def test_clock_offset_uses_the_sample_with_the_smallest_round_trip() -> None:
    # local clock steps: (before, after) pairs of 10 ms, 2 ms and 6 ms round trips; the server is 100 ms ahead of local
    times = iter([0, 10_000_000, 20_000_000, 22_000_000, 30_000_000, 36_000_000])
    servers = iter([105, 121, 133])
    offset, rtt = rec.estimate_clock_offset(lambda: next(servers), samples=3, clock_ns=lambda: next(times))
    assert rtt == pytest.approx(2.0)
    assert offset == pytest.approx(121 - 21.0)
    assert rec.latency_ms(event_ms=1000, recv_ns=905_000_000, offset_ms=100.0) == pytest.approx(5.0)


def test_record_writes_a_csv_that_the_verifier_reads(tmp_path: Path) -> None:
    start = 1_790_000_000_000_000_000
    clock = FakeClock(start)
    # offset ~ 0 (fetch returns local ms), then messages whose event time is 7 ms before they are received
    messages = [_msg(int((start + (i + 20) * 1_000_000) / 1e6) - 7, bid=f"{100 + i}.0", ask=f"{100.1 + i}") for i in range(4)]
    messages.insert(1, "garbage")
    out = tmp_path / "q.csv"
    conn = FakeConnection(messages)
    summary = rec.record(
        "BTCUSDT", seconds=1.0, out=out, connect=lambda url: conn, fetch_time_ms=lambda: int(clock() / 1e6), clock_ns=clock, max_rows=4
    )
    assert conn.closed and summary["rows"] == 4 and Path(summary["path"]) == out
    frame = pd.read_csv(out)
    assert list(frame.columns) == list(rec.COLUMNS) and frame["symbol"].str.endswith("@BINANCE-FUTURES").all()
    q = load_quotes(frame)
    assert len(q) == 4 and q.dropped == 0 and q.venue is not None and set(q.venue) == {"BINANCE-FUTURES"}
    info = quote_quality(q)
    assert info["quotes"] == 4 and summary["latency_ms"]["p50"] == pytest.approx(info["latency_ms"]["p50"], abs=0.01)


def test_record_stops_at_the_deadline_and_keeps_rows_when_the_connection_drops(tmp_path: Path) -> None:
    clock = FakeClock(1_790_000_000_000_000_000)
    conn = FakeConnection([_msg(1)] * 30)
    summary = rec.record("ethusdt", seconds=0.008, out=tmp_path / "d.csv", connect=lambda url: conn, fetch_time_ms=lambda: 0, clock_ns=clock)
    assert 0 < summary["rows"] < 30 and conn.closed

    class Broken(FakeConnection):
        def recv(self) -> str:
            raise ConnectionError("lost")

    broken = Broken([])
    lost = rec.record("btcusdt", seconds=5, out=tmp_path / "e.csv", connect=lambda url: broken, fetch_time_ms=lambda: 0, clock_ns=clock)
    assert broken.closed and lost["rows"] == 0 and "ConnectionError: lost" in lost["stopped_early_by"]
    assert (tmp_path / "e.csv").read_text().startswith("timestamp,")

    class DropsAfterTwo(FakeConnection):
        def recv(self) -> str:
            if not self.messages:
                raise ConnectionError("reset")
            return super().recv()

    partial = rec.record("btcusdt", seconds=5, out=tmp_path / "f.csv", connect=lambda url: DropsAfterTwo([_msg(1), _msg(2)]), fetch_time_ms=lambda: 0, clock_ns=clock)
    assert partial["rows"] == 2 and partial["stopped_early_by"] == "ConnectionError: reset"


def test_summary_counts_negative_latency_and_handles_an_empty_recording() -> None:
    rows = [{"latency_ms": -2.0}, {"latency_ms": 10.0}, {"latency_ms": 20.0}]
    s = rec.summarize(rows, offset_ms=3.0, rtt_ms=1.0)
    assert s["negative_latency_rows"] == 1 and s["clock_offset_ms"] == 3.0 and s["latency_ms"]["p50"] == 10.0
    assert rec.summarize([], 0.0, 0.0)["rows"] == 0
    assert "warning" not in s and s["offset_uncertainty_ms"] == 0.5
    noisy = rec.summarize(rows, offset_ms=3.0, rtt_ms=1200.0)
    assert noisy["offset_uncertainty_ms"] == 600.0 and "not trustworthy" in noisy["warning"]


def test_cli_prints_the_summary(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def fake_record(symbol: str, seconds: float, out: str) -> dict[str, object]:
        seen.update(symbol=symbol, seconds=seconds, out=out)
        return {"rows": 3, "warning": "slow clock"}

    monkeypatch.setattr(rec, "record", fake_record)
    assert rec.main(["--symbol", "ETHUSDT", "--seconds", "5", "--out", str(tmp_path / "x.csv")]) == 0
    assert seen["symbol"] == "ETHUSDT" and seen["seconds"] == 5.0
    text = capsys.readouterr().out
    assert '"rows": 3' in text and "verify --quotes" in text and "proxy or VPN" in text and "WARNING: slow clock" in text


class FakeHttpConnection:
    """Answers each request with a server time; ``fail_on`` makes chosen calls raise like a dropped connection."""

    instances: list[FakeHttpConnection] = []

    def __init__(self, fail_on: tuple[int, ...] = ()) -> None:
        self.calls, self.fail_on = 0, fail_on
        FakeHttpConnection.instances.append(self)

    def request(self, method: str, path: str) -> None:
        self.calls += 1
        if self.calls in self.fail_on:
            raise ConnectionResetError("dropped")
        assert (method, path) == ("GET", rec.TIME_PATH)

    def getresponse(self) -> FakeHttpConnection:
        return self

    def read(self) -> bytes:
        return json.dumps({"serverTime": 1_790_000_000_000 + self.calls}).encode()


def test_time_client_reuses_one_connection() -> None:
    FakeHttpConnection.instances.clear()
    client = rec.TimeClient(factory=FakeHttpConnection)
    assert [client() for _ in range(3)] == [1_790_000_000_001, 1_790_000_000_002, 1_790_000_000_003]
    assert len(FakeHttpConnection.instances) == 1


def test_time_client_reconnects_once_and_then_gives_up() -> None:
    FakeHttpConnection.instances.clear()
    client = rec.TimeClient(factory=lambda: FakeHttpConnection(fail_on=(2,)))
    assert client() == 1_790_000_000_001
    assert client() == 1_790_000_000_001  # the second request on the first connection dropped; a fresh connection answers
    assert len(FakeHttpConnection.instances) == 2
    broken = rec.TimeClient(factory=lambda: FakeHttpConnection(fail_on=(1,)))
    with pytest.raises(ConnectionResetError):
        broken()
