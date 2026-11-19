"""Point-in-time contract of a data table: when was each value published, and who was in the universe?

A backtest that reads a value before it was public, or trades a symbol before it was listed or after it was dropped, is
wrong in a way price data cannot show. This validator checks what the table itself can prove:

* ``published_at`` is present and not earlier than the ``event_time`` it describes (a value cannot be known before it
  happened); a missing publication time means point-in-time use cannot be shown, which is a warning, not a pass;
* every row of a symbol lies inside that symbol's membership interval (``symbol, start, end``), if intervals are given;
  without intervals a universe cannot be shown to be point-in-time (survivorship), which is a warning.

It cannot prove that a vendor's ``published_at`` is honest or that the intervals are complete: that needs a
point-in-time database, which this package does not have (see ``docs/guides/coverage-limits.md``).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from monte_neo.verify.checks import check


def validate_data_contract(
    frame: pd.DataFrame,
    *,
    time_col: str = "timestamp",
    event_col: str | None = None,
    published_col: str | None = None,
    symbol_col: str | None = None,
    membership: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Check rows ``publication_dates`` and ``universe_membership`` for ``frame``.

    Args:
        frame: The table the strategy reads.
        time_col: Column the strategy aligns on (bar time).
        event_col: Column with the time the value describes (for example period end); optional.
        published_col: Column with the time the value became public; ``None`` means not provided.
        symbol_col: Symbol column for universe checks.
        membership: Table ``symbol, start, end`` (``end`` empty or NaT for still a member); ``None`` means not provided.

    Returns:
        Two check rows. ``fail`` for a value published before it happened, a value used before it was published
        (``time_col`` earlier than ``published_col``) or rows outside membership; ``warn`` when the evidence is missing.

    Raises:
        ValueError: A named column is missing from the table.
    """
    for col in (time_col, event_col, published_col, symbol_col):
        if col is not None and col not in frame.columns:
            raise ValueError(f"column {col!r} not found; columns: {', '.join(map(str, frame.columns))}")
    return [_publication_row(frame, time_col, event_col, published_col), _membership_row(frame, time_col, symbol_col, membership)]


def _publication_row(frame: pd.DataFrame, time_col: str, event_col: str | None, published_col: str | None) -> dict[str, Any]:
    if published_col is None:
        return check("publication_dates", "lookahead", "warn",
                     "no publication time given: the table cannot be shown to be point-in-time (values may be used before they were public)")
    pub = pd.to_datetime(frame[published_col], errors="coerce")
    used = pd.to_datetime(frame[time_col], errors="coerce")
    missing = int(pub.isna().sum())
    early_use = int((used < pub).sum())
    before_event = int((pub < pd.to_datetime(frame[event_col], errors="coerce")).sum()) if event_col else 0
    lag = (pub - pd.to_datetime(frame[event_col], errors="coerce")).dt.total_seconds().median() if event_col else None
    det = {"rows": len(frame), "missing_published": missing, "used_before_published": early_use,
           "published_before_event": before_event, "median_lag_seconds": None if lag is None or pd.isna(lag) else float(lag)}
    problems = [f"{c} {t}" for c, t in ((early_use, "rows used before they were published"),
                                        (before_event, "values published before the event they describe")) if c]
    if problems:
        return check("publication_dates", "lookahead", "fail", "look-ahead in the data: " + ", ".join(problems), det)
    if missing:
        return check("publication_dates", "lookahead", "warn", f"{missing} rows have no publication time: point-in-time use is not shown for them", det)
    return check("publication_dates", "lookahead", "pass", "every row is used at or after its publication time", det)


def _membership_row(frame: pd.DataFrame, time_col: str, symbol_col: str | None, membership: pd.DataFrame | None) -> dict[str, Any]:
    if symbol_col is None:
        return check("universe_membership", "lookahead", "skip", "single instrument: no universe to check")
    if membership is None:
        return check("universe_membership", "lookahead", "warn",
                     "no membership dates given: the universe cannot be shown to be point-in-time (survivorship)")
    need = {"symbol", "start"}
    if not need <= set(membership.columns):
        raise ValueError("membership needs the columns symbol, start (and optionally end)")
    spans = membership.assign(start=pd.to_datetime(membership["start"]),
                              end=pd.to_datetime(membership["end"]) if "end" in membership.columns else pd.NaT)
    rows = frame[[symbol_col, time_col]].assign(_t=pd.to_datetime(frame[time_col]))
    merged = rows.merge(spans, left_on=symbol_col, right_on="symbol", how="left")
    unknown = merged[merged["start"].isna()][symbol_col].nunique()
    inside = (merged["_t"] >= merged["start"]) & (merged["end"].isna() | (merged["_t"] <= merged["end"]))
    keyed = merged.assign(_in=inside).groupby([merged[symbol_col], merged["_t"]])["_in"].any()
    outside = int((~keyed).sum())
    det = {"rows": int(len(rows)), "rows_outside_membership": outside, "symbols_without_dates": int(unknown)}
    if outside:
        return check("universe_membership", "lookahead", "fail",
                     f"{outside} rows are for a symbol outside its membership interval (before it joined or after it left)", det)
    return check("universe_membership", "lookahead", "pass", "every row lies inside its symbol's membership interval", det)


__all__ = ["validate_data_contract"]
