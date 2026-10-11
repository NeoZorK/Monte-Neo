"""Load and align a prices universe and a scores table into wide (dates x symbols) matrices.

Forward returns are computed for evaluation only: they are targets, never inputs to a score.
Missing values stay NaN; nothing is forward-filled.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.ingest import _read_table
from monte_neo.verify.market import SYMBOL_ALIASES

TIME_ALIASES = ("timestamp", "date", "time", "datetime")
MIN_SYMBOLS = 3


@dataclass
class Panel:
    """Aligned matrices of shape (dates, symbols)."""

    dates: pd.DatetimeIndex
    symbols: list[str]
    close: np.ndarray
    scores: np.ndarray
    volume: np.ndarray | None = None
    n_unmatched_score_rows: int = 0

    @property
    def periods_per_year(self) -> float:
        """Observations per year inferred from the median date spacing (daily bars count 252)."""
        if len(self.dates) < 2:
            return 252.0
        step = float(np.median(np.diff(self.dates.to_numpy().astype("datetime64[ns]").astype(np.int64)))) / 1e9  # unit-safe
        if step <= 0:
            return 252.0
        return 252.0 if step <= 1.5 * 86400 else 365.25 * 86400 / step

    def forward_returns(self, horizon: int = 1) -> np.ndarray:
        """``close[t+h] / close[t] - 1``; the last ``h`` rows are NaN. For evaluation only."""
        if horizon < 1:
            raise ValueError("horizon must be >= 1")
        out = np.full_like(self.close, np.nan)
        if horizon < len(self.close):
            with np.errstate(divide="ignore", invalid="ignore"):
                out[:-horizon] = self.close[horizon:] / self.close[:-horizon] - 1.0
        out[~np.isfinite(out)] = np.nan
        return out


def _frame(source: pd.DataFrame | str | Path) -> pd.DataFrame:
    df = source.copy() if isinstance(source, pd.DataFrame) else _read_table(Path(source))
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def _pick(df: pd.DataFrame, aliases: tuple[str, ...], what: str) -> str:
    for name in aliases:
        if name in df.columns:
            return name
    raise ValueError(f"missing {what} column (one of {', '.join(aliases)}); found: {', '.join(df.columns)}")


def _normalise(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    tcol = _pick(df, TIME_ALIASES, "timestamp")
    scol = _pick(df, SYMBOL_ALIASES, "symbol")
    if value_col not in df.columns:
        raise ValueError(f"missing '{value_col}' column; found: {', '.join(df.columns)}")
    ts = pd.to_datetime(df[tcol], errors="coerce", utc=True)
    if ts.isna().any():
        raise ValueError(f"{int(ts.isna().sum())} unparseable timestamps in column '{tcol}'")
    out = pd.DataFrame({"timestamp": ts.dt.tz_localize(None), "symbol": df[scol].astype(str).str.strip()})
    out[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    if "volume" in df.columns and value_col == "close":
        out["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    if out.duplicated(["timestamp", "symbol"]).any():
        n = int(out.duplicated(["timestamp", "symbol"]).sum())
        which = "scores" if value_col == "score" else "prices"
        raise ValueError(f"{n} duplicate (timestamp, symbol) rows in the {which} table")
    return out


def build_panel(prices: pd.DataFrame | str | Path, scores: pd.DataFrame | str | Path) -> Panel:
    """Align a long prices table and a long scores table into a :class:`Panel`.

    Args:
        prices: Table with ``timestamp``, ``symbol`` (or ticker/asset/instrument), ``close``
            and optional ``volume``; a DataFrame or a .csv / .parquet path.
        scores: Table with ``timestamp`` (or ``date``), ``symbol`` and ``score``.

    Returns:
        Panel with close, score and (optional) volume matrices on the price dates.

    Raises:
        ValueError: duplicates, scores for unknown symbols, scores dated after the last price,
            fewer than 3 symbols, or no date with at least 3 scored symbols.
    """
    px = _normalise(_frame(prices), "close")
    sc = _normalise(_frame(scores), "score")
    dates = pd.DatetimeIndex(sorted(px["timestamp"].unique()))
    symbols = sorted(px["symbol"].unique())
    if len(symbols) < MIN_SYMBOLS:
        raise ValueError(f"need at least {MIN_SYMBOLS} symbols in the prices table, got {len(symbols)}")
    unknown = sorted(set(sc["symbol"]) - set(symbols))
    if unknown:
        raise ValueError(f"scores contain symbols missing from prices: {', '.join(unknown[:5])}")
    last = dates[-1]
    late = sc["timestamp"] > last
    if late.any():
        raise ValueError(f"{int(late.sum())} score rows are dated after the last price ({last}); drop them")
    close = px.pivot(index="timestamp", columns="symbol", values="close").reindex(index=dates, columns=symbols)
    volume = None
    if "volume" in px.columns:
        volume = px.pivot(index="timestamp", columns="symbol", values="volume").reindex(index=dates, columns=symbols).to_numpy(float)
    aligned = sc[sc["timestamp"].isin(dates)]
    unmatched = len(sc) - len(aligned)
    if aligned.empty:
        raise ValueError("no score date matches a price date")
    wide = aligned.pivot(index="timestamp", columns="symbol", values="score").reindex(index=dates, columns=symbols)
    mat = wide.to_numpy(float, copy=True)
    mat[~np.isfinite(mat)] = np.nan
    if int(np.max(np.isfinite(mat).sum(axis=1))) < MIN_SYMBOLS:
        raise ValueError(f"fewer than {MIN_SYMBOLS} symbols have a score on any single date")
    cl = close.to_numpy(float, copy=True)
    cl[cl <= 0] = np.nan
    return Panel(dates, symbols, cl, mat, volume, unmatched)


def data_sha256(source: Any) -> str:
    """SHA-256 of a file's bytes, or of a DataFrame's canonical CSV text."""
    if isinstance(source, pd.DataFrame):
        return hashlib.sha256(source.to_csv(index=False).encode()).hexdigest()
    return hashlib.sha256(Path(source).read_bytes()).hexdigest()


__all__ = ["MIN_SYMBOLS", "Panel", "build_panel", "data_sha256"]
