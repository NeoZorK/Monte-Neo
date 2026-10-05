"""Data doctor: what is known to be wrong with the export of a data provider, before any strategy touches it.

``diagnose`` recognises the column layout of a provider (Binance klines, Yahoo, Polygon, Databento, TradingView,
MetaTrader 5) and reports the traps of that provider next to generic checks on the table itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROVIDERS = ("binance", "yahoo", "polygon", "databento", "tradingview", "mt5")
_TIME_COLUMNS = ("timestamp", "time", "date", "datetime", "open_time", "t", "ts_event", "close_time")


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().strip("<>").strip().lower().replace(" ", "_") for c in out.columns]
    return out


def detect(columns: list[str]) -> tuple[str | None, float]:
    """The provider whose layout matches the columns best, and how much of the layout matched."""
    cols = set(columns)
    layouts = {
        "binance": {"open_time", "close_time", "quote_volume", "number_of_trades", "taker_buy_base_volume", "taker_buy_quote_volume"},
        "yahoo": {"date", "adj_close", "open", "high", "low", "close", "volume"},
        "polygon": {"o", "h", "l", "c", "v", "t", "vw", "n"},
        "databento": {"ts_event", "rtype", "publisher_id", "instrument_id", "open", "high", "low", "close", "volume"},
        "mt5": {"date", "time", "open", "high", "low", "close", "tickvol", "vol", "spread", "tick_volume", "real_volume"},
        "tradingview": {"time", "open", "high", "low", "close"},
    }
    # A layout counts only when the column that is particular to the provider is there.
    required = {
        "binance": {"open_time"}, "yahoo": {"adj_close"}, "polygon": {"t", "o"}, "databento": {"ts_event"},
        "mt5": {"tickvol", "tick_volume", "spread", "real_volume"}, "tradingview": {"time"},
    }
    best, score = None, 0.0
    for name, layout in layouts.items():
        if not cols & required[name]:
            continue
        hit = len(cols & layout) / len(layout)
        if name == "mt5" and not ({"tickvol", "tick_volume", "spread"} & cols):
            hit *= 0.5
        if name == "tradingview" and ({"adj_close", "tickvol", "spread", "ts_event", "open_time"} & cols):
            hit *= 0.5
        if hit > score:
            best, score = name, hit
    return (best, round(score, 2)) if score >= 0.6 else (None, round(score, 2))


def _finding(level: str, code: str, message: str, advice: str) -> dict[str, str]:
    return {"level": level, "code": code, "message": message, "advice": advice}


def _epoch_unit(values: pd.Series) -> str | None:
    v = pd.to_numeric(values, errors="coerce").dropna().abs()
    if v.empty:
        return None
    m = float(v.median())
    for unit, lo in (("seconds", 1e8), ("milliseconds", 1e11), ("microseconds", 1e14), ("nanoseconds", 1e17)):
        nxt = {"seconds": 1e11, "milliseconds": 1e14, "microseconds": 1e17, "nanoseconds": 1e20}[unit]
        if lo <= m < nxt:
            return unit
    return None


def diagnose(table: pd.DataFrame | str | Path, provider: str = "auto") -> dict[str, Any]:
    """Findings for a raw price table (``provider`` ``auto`` guesses it from the columns)."""
    if provider != "auto" and provider not in PROVIDERS:
        raise ValueError(f"provider must be auto or one of {PROVIDERS}, got {provider!r}")
    if isinstance(table, str | Path):
        from monte_neo.verify.ingest import _read_table

        table = _read_table(Path(table))
    df = _clean(table)
    guess, conf = detect(list(df.columns)) if provider == "auto" else (provider, 1.0)
    found: list[dict[str, str]] = []
    add = found.append

    time_col = next((c for c in _TIME_COLUMNS if c in df.columns), None)
    time_values: pd.Series | None = None
    if guess == "mt5" and "date" in df.columns and "time" in df.columns:
        time_values = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str), errors="coerce")
        time_col = "date+time"
    elif time_col is not None:
        raw = df[time_col]
        if pd.api.types.is_numeric_dtype(raw):
            unit = _epoch_unit(raw)
            if unit is None:
                add(_finding("warn", "epoch_unit", f"column {time_col!r} is numeric but not an epoch in seconds, ms, µs or ns", "Convert it to a date-time yourself and check the first and last stamps."))
            else:
                if unit != "seconds":
                    add(_finding("info", "epoch_unit", f"{time_col!r} is an epoch in {unit}", f"Read it with unit={unit[:2] if unit != 'seconds' else 's'!r}; Binance spot switched to microseconds in 2025, and mixed units in one file are an error."))
                time_values = pd.to_datetime(raw, unit={"seconds": "s", "milliseconds": "ms", "microseconds": "us", "nanoseconds": "ns"}[unit], errors="coerce")
        else:
            time_values = pd.to_datetime(raw, errors="coerce", utc=False, format="mixed")
    else:
        add(_finding("warn", "no_time_column", "no time column was found", "Add a timestamp column: without it annualisation, calendar rules and gap checks are guesses."))

    if time_values is not None:
        stamps = pd.Series(time_values)
        bad = int(stamps.isna().sum())
        if bad:
            add(_finding("error", "unparseable_time", f"{bad} time values cannot be parsed", "Fix or drop those rows; mixed date formats are common after merging exports."))
        valid = stamps.dropna()
        if len(valid) > 1:
            if not valid.is_monotonic_increasing:
                add(_finding("error", "unsorted", "rows are not sorted oldest-first", "Sort by time: on newest-first data shift(1) reads the next bar."))
            dup = int(valid.duplicated().sum())
            if dup:
                add(_finding("error", "duplicate_times", f"{dup} repeated time stamps", "Drop or merge the duplicates (a restart of a download often repeats the boundary bar)."))
            if getattr(valid.dt, "tz", None) is None and guess in ("yahoo", "tradingview", "mt5"):
                where = {"yahoo": "the exchange's local calendar day", "tradingview": "the chart's time zone", "mt5": "the broker's server time (often UTC+2 or UTC+3 with daylight saving)"}[guess]
                add(_finding("warn", "timezone", f"{guess} time stamps have no zone: they are in {where}", "Convert to UTC before joining with other data or using hour-of-day rules."))
            step = valid.diff().dropna()
            median = step.median()
            if pd.notna(median) and median > pd.Timedelta(0):
                gaps = int((step > median * 1.5).sum())
                if gaps:
                    add(_finding("info", "gaps", f"{gaps} gaps longer than 1.5x the usual {median}", "Weekends and holidays are normal; gaps in a 24/7 market are missing bars: forward-filled data hides them."))

    price_cols = [c for c in ("open", "high", "low", "close", "o", "h", "l", "c") if c in df.columns]
    if price_cols:
        arr = df[price_cols].apply(pd.to_numeric, errors="coerce")
        top = float(np.nanmedian(arr.to_numpy()))
        integer_like = bool(np.all(np.isnan(arr.to_numpy()) | (arr.to_numpy() == np.round(arr.to_numpy()))))
        if guess == "databento" and top > 1e7 and integer_like:
            add(_finding("error", "fixed_point_prices", "prices are fixed-point integers (1e-9 units)", "Divide by 1e9 before verifying; otherwise returns are right but every price-level rule is wrong."))
        elif top > 1e9:
            add(_finding("warn", "huge_prices", f"median price {top:.3g} looks like a scaled integer", "Check the vendor's price scale."))
    vol = next((c for c in ("volume", "v", "tick_volume", "tickvol", "vol") if c in df.columns), None)
    if vol is not None:
        zeros = float((pd.to_numeric(df[vol], errors="coerce").fillna(0) == 0).mean())
        if zeros > 0.01:
            add(_finding("warn", "zero_volume", f"{zeros:.1%} of bars have zero volume", "Costs and capacity are not defined on them: filter them or treat the bar as not tradable."))
    if guess == "mt5" and vol in ("tickvol", "tick_volume"):
        add(_finding("info", "tick_volume", "MetaTrader volume is a tick count, not traded volume", "Do not read it as liquidity; capacity estimates from it are not money."))
    if guess == "yahoo" and "adj_close" in df.columns and "close" in df.columns:
        a, c = pd.to_numeric(df["adj_close"], errors="coerce"), pd.to_numeric(df["close"], errors="coerce")
        if bool(((a - c).abs() / c > 1e-4).any()):
            add(_finding("warn", "adjusted_prices", "Adj Close differs from Close: open, high, low and close are on a different basis than the adjusted close", "Scale open/high/low by Adj Close / Close (or use only unadjusted prices) so the bar is internally consistent; mixing bases creates fake gaps at every dividend."))
    if guess == "tradingview":
        extra = [c for c in df.columns if c not in {"time", "open", "high", "low", "close", "volume", "volume_ma"}]
        if extra:
            add(_finding("warn", "indicator_columns", f"the export has indicator columns ({', '.join(extra[:5])}): they were drawn on the whole chart", "Indicator plots can repaint and may use the bar's own close; do not feed them to a strategy, recompute them from the prices."))
    if guess is not None:
        label = {"binance": "open_time marks the bar's start", "yahoo": "the date marks the session's start", "polygon": "t is the bar's start (ms)", "databento": "ts_event is the bar's start", "tradingview": "time is the bar's start", "mt5": "the time is the bar's start"}[guess]
        add(_finding("info", "bar_label", f"{guess}: {label}", "A bar is complete only at its end: a signal that reads the row may trade no earlier than the next bar's open."))
    if "symbol" in df.columns and df["symbol"].nunique() > 1:
        add(_finding("info", "universe", f"{df['symbol'].nunique()} symbols in one table", "Verify as a universe: delisted symbols are probably missing (survivorship)."))
    levels = [f["level"] for f in found]
    return {
        "provider": guess, "confidence": conf, "rows": int(len(df)), "time_column": time_col,
        "status": "error" if "error" in levels else "warn" if "warn" in levels else "ok",
        "findings": found,
    }


__all__ = ["PROVIDERS", "detect", "diagnose"]
