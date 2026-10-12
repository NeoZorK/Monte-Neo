"""Point-in-time events: load them and join them to bars by publication time.

An event (earnings surprise, news sentiment, alternative data, an LLM output) has two
times: ``event_time`` (when the underlying fact happened, e.g. the fiscal quarter end)
and ``published_at`` (when the world could first see it). A strategy that joins events
by ``event_time`` trades on facts nobody knew yet: look-ahead hidden in the data join.

Bar-timestamp convention: bars are stamped at their OPEN (as in the rest of the verifier,
a signal read at bar t fills at the open of bar t+1). The conservative rule used here:
an event is visible on the first bar whose open time is strictly after the key time plus
the delay. An event published during bar t, or exactly at its open, is usable from t+1.
Before the first event the joined columns are NaN; nothing is filled backward.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from monte_neo.verify.ingest import _read_table

TIME_ALIASES = ("published_at", "published", "publication_time", "publish_time", "release_time", "release_date")
EVENT_ALIASES = ("event_time", "event_date", "period_end")
SYMBOL_ALIASES = ("symbol", "ticker", "asset", "instrument")
BAR_TIME_ALIASES = ("timestamp", "time", "date", "datetime", "open_time")


def to_naive_utc(values: pd.Series, what: str = "time") -> pd.Series:
    """Parse times to UTC and drop the zone (naive UTC, as the rest of the verifier).

    Numbers are epoch seconds, milliseconds, microseconds or nanoseconds (guessed by size).

    Raises:
        ValueError: when a non-empty value cannot be parsed.
    """
    s = values.reset_index(drop=True)
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
        top = float(np.nanmax(np.abs(s.to_numpy(dtype=np.float64)))) if len(s) else 0.0
        unit = "ns" if top > 1e17 else "us" if top > 1e14 else "ms" if top > 1e11 else "s"
        out = pd.to_datetime(s, unit=unit, utc=True, errors="coerce")
    else:
        out = pd.to_datetime(s, utc=True, errors="coerce", format="mixed")
    bad = out.isna() & s.notna()
    if bool(bad.any()):
        raise ValueError(f"cannot parse {what}: row {int(bad.idxmax())} value {s[bad].iloc[0]!r}")
    return out.dt.tz_convert(None).astype("datetime64[ns]")


def _rename_first(df: pd.DataFrame, target: str, aliases: tuple[str, ...]) -> pd.DataFrame:
    if target in df.columns:
        return df
    for alias in aliases:
        if alias in df.columns:
            return df.rename(columns={alias: target})
    return df


def load_events(source: pd.DataFrame | str | Path) -> pd.DataFrame:
    """Read an events table: ``published_at``, optional ``event_time`` / ``symbol``, numeric value columns.

    Times become naive UTC. Rows are sorted by (symbol, published_at); the original order
    does not matter for events.

    Args:
        source: A DataFrame or a CSV or parquet path.

    Returns:
        Columns ``published_at``, ``event_time`` (when given), ``symbol`` (when given) and values.

    Raises:
        ValueError: missing ``published_at``, unparseable times, no numeric value column,
            or a duplicate (symbol, published_at) row (reports the first).
    """
    from monte_neo.verify.ingest import as_pandas

    source = as_pandas(source)  # a polars table is accepted like a pandas one
    df = source.copy() if isinstance(source, pd.DataFrame) else _read_table(Path(source))
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = _rename_first(df, "published_at", TIME_ALIASES)
    df = _rename_first(df, "event_time", EVENT_ALIASES)
    df = _rename_first(df, "symbol", SYMBOL_ALIASES)
    if "published_at" not in df.columns:
        raise ValueError("events are missing the published_at column (when each event became public)")
    df = df.reset_index(drop=True)
    df["published_at"] = to_naive_utc(df["published_at"], "published_at")
    if bool(df["published_at"].isna().any()):
        raise ValueError(f"published_at is empty in row {int(df['published_at'].isna().idxmax())}")
    if "event_time" in df.columns:
        df["event_time"] = to_naive_utc(df["event_time"], "event_time")
    if "symbol" in df.columns:
        if bool(df["symbol"].isna().any()):
            raise ValueError(f"{int(df['symbol'].isna().sum())} events have no symbol")
        df["symbol"] = df["symbol"].astype(str)
    meta = {"published_at", "event_time", "symbol"}
    values = [c for c in df.columns if c not in meta]
    for col in values:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(np.float64)
    values = [c for c in values if bool(df[c].notna().any())]
    if not values:
        raise ValueError("events have no numeric value column")
    keys = [c for c in ("symbol", "published_at") if c in df.columns]
    dup = df.duplicated(subset=keys, keep=False)
    if bool(dup.any()):
        first = df.loc[dup, keys].iloc[0].to_dict()
        raise ValueError(f"duplicate events for {first}: one row per (symbol, published_at) is required")
    cols = keys + [c for c in ("event_time",) if c in df.columns] + values
    return df[cols].sort_values(keys, kind="stable").reset_index(drop=True)


def bar_times(ohlcv: pd.DataFrame) -> pd.Series:
    """The OHLCV bar open times as naive UTC.

    Raises:
        ValueError: when the OHLCV has no time column.
    """
    for name in BAR_TIME_ALIASES:
        if name in ohlcv.columns:
            return to_naive_utc(ohlcv[name], "OHLCV timestamp")
    if isinstance(ohlcv.index, pd.DatetimeIndex):
        return to_naive_utc(pd.Series(ohlcv.index), "OHLCV timestamp")
    raise ValueError("the OHLCV needs a timestamp column to join events")


def join_events(
    ohlcv: pd.DataFrame,
    events: pd.DataFrame,
    *,
    by: str = "published_at",
    delay: pd.Timedelta | str | int = 0,
    prefix: str = "ev_",
) -> pd.DataFrame:
    """As-of join events to bars: add ``<prefix><column>`` to a copy of ``ohlcv``.

    Each bar gets the latest event whose key time plus ``delay`` is strictly before the
    bar's open time (an event published during bar t shows up on bar t+1). Per symbol for
    a universe. Rows keep their order; bars before the first event get NaN.

    Args:
        ohlcv: Bars with a time column (and ``symbol`` for a universe).
        events: Output of :func:`load_events`.
        by: ``published_at`` (honest) or ``event_time`` (the leaky join, for comparison).
        delay: Extra lag added to the key time (``Timedelta``; 0 means none).
        prefix: Column prefix for the joined values.

    Returns:
        A copy of ``ohlcv`` with the event value columns added.

    Raises:
        ValueError: unknown ``by``, negative delay, missing time or symbol column.
    """
    if by not in ("published_at", "event_time"):
        raise ValueError("by must be 'published_at' or 'event_time'")
    if by not in events.columns:
        raise ValueError(f"events have no {by} column")
    lag = pd.Timedelta(delay)
    if lag < pd.Timedelta(0):
        raise ValueError("delay must not be negative")
    out = ohlcv.copy()
    universe = "symbol" in ohlcv.columns
    if universe and "symbol" not in events.columns:
        raise ValueError("the OHLCV is a universe: events need a symbol column")
    values = [c for c in events.columns if c not in ("published_at", "event_time", "symbol")]
    left = pd.DataFrame({"_t": bar_times(ohlcv).to_numpy(), "_row": np.arange(len(out))})
    if bool(left["_t"].isna().any()):
        raise ValueError("the OHLCV has empty timestamps")
    right = events[[c for c in ("symbol", by) if c in events.columns] + values].copy()
    right = right[right[by].notna()].rename(columns={by: "_key"})
    right["_key"] = right["_key"] + lag
    keys: dict[str, object] = {}
    if universe:
        left["symbol"] = ohlcv["symbol"].astype(str).to_numpy()
        keys["by"] = "symbol"
    left = left.sort_values("_t", kind="stable")
    right = right.sort_values("_key", kind="stable")
    merged = pd.merge_asof(left, right, left_on="_t", right_on="_key", direction="backward", allow_exact_matches=False, **keys)
    merged = merged.sort_values("_row", kind="stable")
    for col in values:
        out[f"{prefix}{col}"] = merged[col].to_numpy()
    return out
