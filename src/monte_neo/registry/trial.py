"""``registry try``: public Binance spot daily bars, cached as CSV, and Monte-Neo's verification of the strategy's ``signal(df)``."""

from __future__ import annotations

import datetime as dt
import json
import time
import urllib.parse
from pathlib import Path
from typing import Any

from monte_neo.registry.client import RegistryError, http_get

KLINES = "https://api.binance.com/api/v3/klines"
DAY_MS = 86_400_000
COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


def _ms(day: str, end: bool = False) -> int:
    d = dt.datetime.fromisoformat(day).replace(tzinfo=dt.UTC)
    return int(d.timestamp() * 1000) + (DAY_MS - 1 if end else 0)


def fetch_klines(symbol: str, start_ms: int, end_ms: int) -> list[list[Any]]:
    """Raw Binance daily klines in [start_ms, end_ms], 1000 bars a call. Public data: no key is sent."""
    rows: list[list[Any]] = []
    cursor = start_ms
    while cursor <= end_ms:
        q = urllib.parse.urlencode({"symbol": symbol, "interval": "1d", "startTime": cursor, "endTime": end_ms, "limit": 1000})
        try:
            page = json.loads(http_get(f"{KLINES}?{q}"))
        except ValueError:
            raise RegistryError("Binance answered something that is not JSON", 2) from None
        if not page:
            break
        rows.extend(page)
        cursor = int(page[-1][0]) + DAY_MS
        if len(page) < 1000:
            break
        time.sleep(0.1)
    return rows


def download_csv(symbol: str, start: str, end: str, folder: Path) -> Path:
    """Daily bars of ``symbol`` from ``start`` to ``end`` (YYYY-MM-DD, inclusive) as a CSV in ``folder``; a cached file is reused."""
    path = folder / f"{symbol}_{start}_{end}.csv"
    if path.is_file():
        return path
    now_ms = int(time.time() * 1000)
    raw = [r for r in fetch_klines(symbol, _ms(start), _ms(end, end=True)) if int(r[6]) < now_ms]  # closed bars only
    if not raw:
        raise RegistryError(f"no daily bars for {symbol} between {start} and {end}", 2)
    folder.mkdir(parents=True, exist_ok=True)
    lines = [",".join(COLUMNS)]
    for r in raw:
        day = dt.datetime.fromtimestamp(int(r[0]) / 1000, dt.UTC).strftime("%Y-%m-%d")
        lines.append(",".join([day, str(r[1]), str(r[2]), str(r[3]), str(r[4]), str(r[5])]))
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def run_verify(csv: Path, strategy: Path, n_trials: int, fee_bps: float, slippage_bps: float) -> dict[str, Any]:
    """Monte-Neo's verify on the strategy's ``signal(df)``: long/flat, the costs and trial count of the registry's spec."""
    from monte_neo.verify import load_ohlcv, model_from_costs, verify_strategy
    from monte_neo.verify.market import bar_count

    df = load_ohlcv(csv)
    model = model_from_costs(commission_bps=fee_bps, slippage_bps=slippage_bps, side_mode="long_flat", n_bars=bar_count(df))
    report: dict[str, Any] = verify_strategy(df, strategy=strategy, n_trials=n_trials, model=model)
    return report


def summary(report: dict[str, Any]) -> dict[str, Any]:
    """The few numbers shown side by side."""
    arl = report.get("arl") or {}
    return {
        "verdict": report.get("verdict"),
        "arl": arl.get("level") if isinstance(arl, dict) else arl,
        "certificate_id": report.get("certificate_id"),
        "sharpe": _find(report, ("sharpe_annualized", "sharpe")),
        "deflated_sharpe": _find(report, ("deflated_sharpe", "dsr")),
    }


def _find(obj: Any, keys: tuple[str, ...], depth: int = 0) -> float | None:
    if depth > 4 or not isinstance(obj, dict):
        return None
    for k in keys:
        v = obj.get(k)
        if isinstance(v, int | float) and not isinstance(v, bool):
            return float(v)
    for v in obj.values():
        if isinstance(v, dict):
            found = _find(v, keys, depth + 1)
            if found is not None:
                return found
    return None
