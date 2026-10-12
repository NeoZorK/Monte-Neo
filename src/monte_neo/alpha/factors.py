"""Self-built factor returns from a universe (no external data) and a loader for user factors.

Every long-short factor is strictly causal: the sort at the close of bar ``t-1`` uses data up to
``t-1`` only and earns the return of bar ``t``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from monte_neo.alpha._core import rank_rows

MIN_OVERLAP = 60
_TIME_NAMES = ("timestamp", "date", "time", "datetime")


def _returns(close: np.ndarray) -> np.ndarray:
    ret = np.full(close.shape, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        ret[1:] = close[1:] / close[:-1] - 1.0
    ret[~np.isfinite(ret)] = np.nan
    return ret


def _long_short(signal: np.ndarray, ret: np.ndarray, quantile: float, *, long_high: bool) -> np.ndarray:
    """Return of bar t from the top/bottom ``quantile`` of ``signal[t-1]``, equal weight."""
    sig = signal[:-1] if long_high else -signal[:-1]
    nxt = ret[1:]
    ok = np.isfinite(sig)
    n = ok.sum(axis=1, keepdims=True)
    k = np.maximum(1, np.floor(quantile * n))
    rk = rank_rows(np.where(ok, sig, np.nan))
    top = ok & (rk > n - k)
    bot = ok & (rk <= k)
    out = np.full(len(ret), np.nan)
    for sel, sign in ((top, 1.0), (bot, -1.0)):
        val = np.isfinite(nxt) & sel
        cnt = val.sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            leg = np.where(cnt > 0, np.where(val, nxt, 0.0).sum(axis=1) / cnt, np.nan)
        out[1:] = leg * sign if sign > 0 else out[1:] + leg * sign
    valid = (n[:, 0] >= 2) & np.isfinite(out[1:])
    out[1:] = np.where(valid, out[1:], np.nan)
    return out


def build_factors(
    close: np.ndarray,
    volume: np.ndarray | None,
    dates: pd.DatetimeIndex | pd.Index,
    *,
    quantile: float = 0.2,
) -> pd.DataFrame:
    """Build market, size, momentum, reversal and low-volatility factor returns from a universe.

    Args:
        close: Close prices, shape (T, N); NaN for missing.
        volume: Volumes, shape (T, N), or None (then ``size`` is skipped).
        dates: Index of length T.
        quantile: Share of the universe in each leg of a long-short factor.

    Returns:
        DataFrame indexed by ``dates``. Columns: ``market`` (equal-weight mean return), ``size`` (small minus
        big by 20-bar mean dollar volume), ``momentum`` (12-1, scaled for short histories), ``reversal``
        (losers minus winners of the last 5 bars) and ``low_vol`` (low minus high 60-bar volatility).
        Undefined early rows are NaN.
    """
    close = np.asarray(close, dtype=np.float64)
    t_len = close.shape[0]
    ret = _returns(close)
    cols: dict[str, np.ndarray] = {}
    fin = np.isfinite(ret)
    cnt = fin.sum(axis=1)
    with np.errstate(all="ignore"):
        mk = np.where(cnt > 0, np.where(fin, ret, 0.0).sum(axis=1) / cnt, np.nan)
    cols["market"] = mk
    c = pd.DataFrame(close)
    if volume is not None:
        dv = (c * pd.DataFrame(np.asarray(volume, dtype=np.float64))).rolling(20, min_periods=20).mean().to_numpy()
        cols["size"] = _long_short(dv, ret, quantile, long_high=False)
    lookback = min(252, t_len // 4)
    skip = lookback // 12
    if lookback > skip:
        with np.errstate(all="ignore"):
            mom = c.shift(skip) / c.shift(lookback) - 1.0
        cols["momentum"] = _long_short(mom.to_numpy(), ret, quantile, long_high=True)
    with np.errstate(all="ignore"):
        rev = (c / c.shift(5) - 1.0).to_numpy()
    cols["reversal"] = _long_short(rev, ret, quantile, long_high=False)
    vol = pd.DataFrame(ret).rolling(60, min_periods=60).std().to_numpy()
    cols["low_vol"] = _long_short(vol, ret, quantile, long_high=False)
    out = pd.DataFrame(cols, index=pd.Index(dates))
    out.iloc[0] = np.nan
    return out


def load_factors(path: str | Path, dates: pd.DatetimeIndex | pd.Index) -> pd.DataFrame:
    """Load user factor returns (CSV or parquet) and align them to ``dates`` by inner join.

    The file needs a date column (``date``, ``timestamp``, ``time`` or ``datetime``; otherwise the first
    column) and one column per factor with returns as decimals.

    Args:
        path: CSV or parquet file.
        dates: Dates of the strategy returns.

    Returns:
        Factor DataFrame restricted to the overlapping dates.

    Raises:
        ValueError: If fewer than 60 dates overlap or the file has no factor columns.
    """
    p = Path(path)
    df = pd.read_parquet(p) if p.suffix.lower() in (".parquet", ".pq") else pd.read_csv(p)
    df.columns = [str(c).strip() for c in df.columns]
    tcol = next((c for c in df.columns if c.lower() in _TIME_NAMES), df.columns[0])
    idx = pd.to_datetime(df[tcol], errors="coerce", utc=True).dt.tz_localize(None)
    f = df.drop(columns=[tcol]).apply(pd.to_numeric, errors="coerce")
    f.index = pd.DatetimeIndex(idx)
    f = f[f.index.notna() & ~f.index.duplicated()].dropna(axis=1, how="all")
    if f.shape[1] == 0:
        raise ValueError("factor file has no numeric factor columns")
    want = pd.DatetimeIndex(pd.to_datetime(dates, utc=True)).tz_localize(None)
    common = want.intersection(f.index)
    if len(common) < MIN_OVERLAP:
        common = want.normalize().intersection(f.index.normalize())
        f.index = f.index.normalize()
        f = f[~f.index.duplicated()]
    if len(common) < MIN_OVERLAP:
        raise ValueError(f"factor file overlaps only {len(common)} dates (< {MIN_OVERLAP}); check date range and column")
    return f.loc[common].sort_index()
