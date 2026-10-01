"""Record real top-of-book quotes with their latency from Binance USD-M futures (``bookTicker``).

The stream stamps every update with the exchange's event time ``E`` (milliseconds). The recorder notes when each
message reached this machine and writes ``timestamp, bid, ask, latency_ms, symbol, recv_ns``, the table
:func:`monte_neo.verify.quotes.load_quotes` reads. Run it on the machine and network where the strategy would trade.

What the latency is, and is not:

* ``latency_ms`` = local receive time (corrected by the clock offset to the exchange) - event time ``E``.
  It contains the network path, the exchange's own push delay and your machine; a proxy or VPN inflates it.
* The offset comes from ``/fapi/v1/time`` (the sample with the smallest round trip, error about half of it).
  Right after a clock correction some latencies can be a few ms negative: they are kept, and ``quote_quality`` warns.
* ``E`` has millisecond resolution, so latencies are quantized to 1 ms.
"""

from __future__ import annotations

import argparse
import http.client
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import numpy as np

STREAM_URL = "wss://fstream.binance.com/ws/{symbol}@bookTicker"
TIME_URL = "https://fapi.binance.com/fapi/v1/time"
TIME_HOST, TIME_PATH = "fapi.binance.com", "/fapi/v1/time"
MAX_TRUSTED_UNCERTAINTY_MS = 10.0
COLUMNS = ("timestamp", "bid", "ask", "latency_ms", "symbol", "recv_ns")


class Connection(Protocol):
    """What the recorder needs from a WebSocket: a timed ``recv`` and ``close``."""

    def recv(self) -> str: ...

    def close(self) -> None: ...


def parse_book_ticker(message: str | bytes | dict[str, Any]) -> dict[str, Any] | None:
    """``{event_ms, bid, ask, symbol}`` from a ``bookTicker`` message (also inside a combined-stream frame), else ``None``."""
    try:
        data = json.loads(message) if isinstance(message, str | bytes) else message
        data = data.get("data", data) if isinstance(data, dict) else None
        if not data or data.get("e") != "bookTicker":
            return None
        bid, ask = float(data["b"]), float(data["a"])
        if not (np.isfinite(bid) and np.isfinite(ask)):
            return None
        return {"event_ms": int(data["E"]), "bid": bid, "ask": ask, "symbol": str(data["s"])}
    except (ValueError, KeyError, TypeError):
        return None


def estimate_clock_offset(
    fetch_time_ms: Callable[[], int], *, samples: int = 9, clock_ns: Callable[[], int] = time.time_ns
) -> tuple[float, float]:
    """``(offset_ms, rtt_ms)`` of the exchange clock against this machine, from the round trip with the smallest delay.

    ``offset_ms`` is added to the local time to get exchange time.
    """
    best: tuple[float, float] | None = None
    for _ in range(max(1, samples)):
        before = clock_ns() / 1e6
        server = float(fetch_time_ms())
        after = clock_ns() / 1e6
        rtt = after - before
        if best is None or rtt < best[1]:
            best = (server - (before + after) / 2.0, rtt)
    assert best is not None
    return best


def latency_ms(event_ms: int, recv_ns: int, offset_ms: float) -> float:
    """Receive time on the exchange clock minus the event time, in ms."""
    return recv_ns / 1e6 + offset_ms - event_ms


def write_rows(rows: list[dict[str, Any]], path: str | Path) -> Path:
    """Write the recorded rows as CSV with :data:`COLUMNS`."""
    out = Path(path)
    lines = [",".join(COLUMNS)]
    for r in rows:
        stamp = datetime.fromtimestamp(r["event_ms"] / 1000.0, UTC).strftime("%Y-%m-%d %H:%M:%S.%f") + "+00:00"
        lines.append(f"{stamp},{r['bid']!r},{r['ask']!r},{r['latency_ms']:.3f},{r['symbol']}@BINANCE-FUTURES,{r['recv_ns']}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def summarize(rows: list[dict[str, Any]], offset_ms: float, rtt_ms: float) -> dict[str, Any]:
    """Counts and latency percentiles of a recording."""
    lat = np.array([r["latency_ms"] for r in rows]) if rows else np.array([0.0])
    p50, p95, p99 = (float(x) for x in np.percentile(lat, [50, 95, 99]))
    uncertainty = float(rtt_ms) / 2.0
    out = {
        "rows": len(rows),
        "clock_offset_ms": float(offset_ms),
        "offset_round_trip_ms": float(rtt_ms),
        "offset_uncertainty_ms": uncertainty,
        "latency_ms": {"p50": p50, "p95": p95, "p99": p99},
        "negative_latency_rows": int((lat < 0).sum()),
    }
    if uncertainty > MAX_TRUSTED_UNCERTAINTY_MS:
        out["warning"] = (
            f"the clock offset is only known to about +-{uncertainty:.0f} ms (round trip {rtt_ms:.0f} ms): "
            "latencies are not trustworthy at that scale; a proxy, VPN or slow network is the usual cause"
        )
    return out


def record(
    symbol: str,
    seconds: float,
    out: str | Path,
    *,
    connect: Callable[[str], Connection] | None = None,
    fetch_time_ms: Callable[[], int] | None = None,
    clock_ns: Callable[[], int] = time.time_ns,
    max_rows: int | None = None,
) -> dict[str, Any]:
    """Record ``symbol`` (e.g. ``BTCUSDT``) for ``seconds`` into ``out`` and return the summary.

    A connection that drops mid-way ends the recording: the rows received so far are written and the reason is in
    ``stopped_early_by``.
    """
    connect = connect or _default_connect
    fetch_time_ms = fetch_time_ms or _default_fetch_time()
    offset, rtt = estimate_clock_offset(fetch_time_ms, clock_ns=clock_ns)
    conn = connect(STREAM_URL.format(symbol=symbol.lower()))
    rows: list[dict[str, Any]] = []
    error: str | None = None
    deadline = clock_ns() + int(seconds * 1e9)
    try:
        while clock_ns() < deadline and (max_rows is None or len(rows) < max_rows):
            try:
                message = conn.recv()
            except Exception as exc:  # a lost connection must not lose what was already recorded
                error = f"{type(exc).__name__}: {exc}"
                break
            recv_ns = clock_ns()
            parsed = parse_book_ticker(message)
            if parsed is not None:
                parsed["recv_ns"] = recv_ns
                parsed["latency_ms"] = latency_ms(parsed["event_ms"], recv_ns, offset)
                rows.append(parsed)
    finally:
        conn.close()
    path = write_rows(rows, out)
    return {"path": str(path), "stopped_early_by": error, **summarize(rows, offset, rtt)}


def _default_connect(url: str) -> Connection:  # pragma: no cover - network glue
    try:
        import websocket
    except ImportError as exc:
        raise ImportError('recording needs websocket-client: pip install "monte-neo[data]"') from exc
    return websocket.create_connection(url, timeout=30)


class TimeClient:
    """Exchange time over one keep-alive HTTPS connection.

    A new connection per sample costs a TCP and a TLS handshake on top of the request (about three round trips), which
    inflates the round trip the offset error is judged by. Here only the first sample pays for the handshake.
    """

    def __init__(self, factory: Callable[[], Any] | None = None) -> None:
        self._factory = factory or (lambda: http.client.HTTPSConnection(TIME_HOST, timeout=10))
        self._conn: Any = None

    def __call__(self) -> int:
        for attempt in (0, 1):
            try:
                if self._conn is None:
                    self._conn = self._factory()
                self._conn.request("GET", TIME_PATH)
                return int(json.loads(self._conn.getresponse().read())["serverTime"])
            except (OSError, http.client.HTTPException):
                self._conn = None  # a dropped keep-alive connection: reconnect once
                if attempt:
                    raise
        raise AssertionError("unreachable")  # pragma: no cover


def _default_fetch_time() -> Callable[[], int]:  # pragma: no cover - network glue
    """Keep-alive client on a direct connection; the plain per-request fetch when an HTTPS proxy is configured."""
    from urllib.request import getproxies, urlopen

    if not getproxies().get("https"):
        return TimeClient()

    def through_proxy() -> int:
        with urlopen(TIME_URL, timeout=10) as response:  # noqa: S310 - fixed https URL
            return int(json.load(response)["serverTime"])

    return through_proxy


def main(argv: list[str] | None = None) -> int:
    """``python -m monte_neo.data.quote_recorder --symbol BTCUSDT --seconds 600 --out quotes.csv``."""
    p = argparse.ArgumentParser(prog="python -m monte_neo.data.quote_recorder", description=__doc__.split("\n\n")[0])
    p.add_argument("--symbol", default="BTCUSDT", help="USD-M futures symbol (default BTCUSDT)")
    p.add_argument("--seconds", type=float, default=600.0, help="Recording length (default 600)")
    p.add_argument("--out", default="quotes.csv", help="Output CSV (default quotes.csv)")
    args = p.parse_args(argv)
    summary = record(args.symbol, args.seconds, args.out)
    print(json.dumps(summary, indent=2))
    if summary.get("warning"):
        print(f"WARNING: {summary['warning']}")
    print(
        "Check it with: monte-neo verify --quotes "
        f"{args.out} --strategy my_strategy.py --bar-ms 1000\n"
        "Latency includes your network path (and any proxy or VPN): record where the strategy would trade."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

__all__ = ["TimeClient", "estimate_clock_offset", "latency_ms", "main", "parse_book_ticker", "record", "summarize", "write_rows"]
