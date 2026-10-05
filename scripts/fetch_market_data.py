"""Download public market data into the CSV layout ``monte-neo`` reads (timestamp, open, high, low, close, volume).

Sources (no key, no account):
  binance  monthly kline archives from https://data.binance.vision (spot, any symbol and interval)
  stooq    daily history from https://stooq.com (ETFs and stocks: spy.us, qqq.us, gld.us, tlt.us ...)

Examples:
  python scripts/fetch_market_data.py binance --symbol BTCUSDT --interval 1h --start 2021-01 --end 2024-12 --out data/real/btc_1h.csv
  python scripts/fetch_market_data.py stooq --symbol spy.us --out data/real/spy_1d.csv

The data stays on your machine; check each source's terms before you publish anything derived from it.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

BINANCE_URL = "https://data.binance.vision/data/spot/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{month}.zip"
STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"
HEADER = ["timestamp", "open", "high", "low", "close", "volume"]


def _epoch_to_iso(value: str) -> str:
    """Binance open times are milliseconds, and microseconds in archives from 2025 on."""
    v = int(value)
    seconds = v / 1e6 if v > 10**14 else v / 1e3
    return datetime.fromtimestamp(seconds, tz=UTC).strftime("%Y-%m-%d %H:%M:%S+00:00")


def parse_binance_zip(payload: bytes) -> list[list[str]]:
    """Rows ``[timestamp, open, high, low, close, volume]`` of one kline archive (with or without a header row)."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        text = archive.read(archive.namelist()[0]).decode("utf-8")
    rows = []
    for rec in csv.reader(io.StringIO(text)):
        if not rec or not rec[0].strip().isdigit():
            continue  # a header row
        rows.append([_epoch_to_iso(rec[0]), rec[1], rec[2], rec[3], rec[4], rec[5]])
    return rows


def parse_stooq(text: str) -> list[list[str]]:
    """Rows of a Stooq daily CSV (Date, Open, High, Low, Close, Volume); an error page raises."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines or not lines[0].lower().startswith("date"):
        raise ValueError(f"Stooq did not return a table: {text[:80]!r}")
    return [[r[0], r[1], r[2], r[3], r[4], r[5] if len(r) > 5 else "0"] for r in csv.reader(lines[1:])]


def months(start: str, end: str) -> list[str]:
    y, m = (int(x) for x in start.split("-"))
    y2, m2 = (int(x) for x in end.split("-"))
    out = []
    while (y, m) <= (y2, m2):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "monte-neo-fetch/1"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - fixed https hosts above
        return resp.read()


def write(rows: list[list[str]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(HEADER)
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="source", required=True)
    b = sub.add_parser("binance")
    b.add_argument("--symbol", required=True, help="for example BTCUSDT")
    b.add_argument("--interval", default="1h", help="1m 5m 15m 1h 4h 1d (default 1h)")
    b.add_argument("--start", required=True, help="first month, YYYY-MM")
    b.add_argument("--end", required=True, help="last month, YYYY-MM")
    s = sub.add_parser("stooq")
    s.add_argument("--symbol", required=True, help="for example spy.us")
    for q in (b, s):
        q.add_argument("--out", required=True)
    args = p.parse_args(argv)
    try:
        if args.source == "binance":
            rows: list[list[str]] = []
            for month in months(args.start, args.end):
                url = BINANCE_URL.format(symbol=args.symbol.upper(), interval=args.interval, month=month)
                try:
                    rows += parse_binance_zip(_get(url))
                except urllib.error.HTTPError as exc:
                    print(f"  {month}: {exc.code} (not published yet or no such symbol), skipped", file=sys.stderr)
                else:
                    print(f"  {month}: ok", file=sys.stderr)
        else:
            rows = parse_stooq(_get(STOOQ_URL.format(symbol=args.symbol.lower())).decode("utf-8", errors="replace"))
    except (urllib.error.URLError, ValueError, zipfile.BadZipFile) as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 3
    if not rows:
        print("no rows downloaded", file=sys.stderr)
        return 3
    write(rows, Path(args.out))
    print(f"wrote {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
