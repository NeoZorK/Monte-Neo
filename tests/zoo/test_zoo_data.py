"""Data defects: every injected defect must be flagged by a data check, clean tables must not be (class A4)."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import verify_strategy

FREQS = {"daily": ("1D", 1500), "hourly": ("1h", 2500), "minute": ("1min", 2500)}


def clean(freq: str, seed: int = 1) -> pd.DataFrame:
    rule, n = FREQS[freq]
    df = synthetic_ohlcv(n, seed=seed)
    df["timestamp"] = pd.date_range("2021-01-04", periods=n, freq=rule)
    return df


def _sma(d: pd.DataFrame) -> np.ndarray:
    return np.where(d["close"].rolling(20).mean() > d["close"].rolling(60).mean(), 1, 0)


def _set(df: pd.DataFrame, rows: slice | list[int], col: str, value: float) -> pd.DataFrame:
    out = df.copy()
    out.loc[out.index[rows] if isinstance(rows, slice) else rows, col] = value
    return out


def _spikes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for i in range(100, len(df) - 50, 150):
        out.loc[i, ["open", "high", "low", "close"]] = out.loc[i, "close"] * 1.25
    return out


def _frozen(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    block = out.index[400:460]
    out.loc[block, ["open", "high", "low", "close"]] = out.loc[399, "close"]
    return out


def _split(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    k = len(df) * 2 // 5
    out.loc[k:, ["open", "high", "low", "close"]] = out.loc[k:, ["open", "high", "low", "close"]] / 2
    out.loc[k:, "volume"] = out.loc[k:, "volume"] * 2
    return out


def _outage(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(df.index[600:660]).reset_index(drop=True)


def _sparse_gaps(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(df.index[np.arange(50, len(df), 40)]).reset_index(drop=True)


def _zero_volume(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.loc[out.index[::5], "volume"] = 0.0
    return out


def _stale_repeat(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    cols = ["open", "high", "low", "close", "volume"]
    out.loc[out.index[700:740], cols] = out.loc[699, cols].to_numpy()
    return out


def _jump(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    cols = ["open", "high", "low", "close"]
    out.loc[900:, cols] = out.loc[900:, cols] * 10
    return out


# (name, function, which check family is expected to flag it)
DEFECTS = [
    ("duplicate_row", lambda d: pd.concat([d, d.iloc[[300]]]).sort_index(kind="stable").reset_index(drop=True), "integrity"),
    ("duplicate_block", lambda d: pd.concat([d.iloc[:500], d.iloc[480:500], d.iloc[500:]]).reset_index(drop=True), "integrity"),
    ("swapped_rows", lambda d: d.iloc[np.r_[0:200, 201, 200, 202:len(d)]].reset_index(drop=True), "integrity"),
    ("newest_first", lambda d: d.iloc[::-1].reset_index(drop=True), "integrity"),
    ("shuffled_rows", lambda d: d.sample(frac=1.0, random_state=3).reset_index(drop=True), "integrity"),
    ("high_below_low", lambda d: _set(d, [400, 401], "high", 1.0), "integrity"),
    ("close_above_high", lambda d: d.assign(close=d["high"] * 1.05), "integrity"),
    ("open_below_low", lambda d: d.assign(open=d["low"] * 0.95), "integrity"),
    ("nan_close", lambda d: _set(d, [250, 251], "close", np.nan), "integrity"),
    ("nan_high", lambda d: _set(d, [250], "high", np.nan), "integrity"),
    ("inf_open", lambda d: _set(d, [250], "open", np.inf), "integrity"),
    ("zero_price", lambda d: _set(d, [300], "close", 0.0), "integrity"),
    ("negative_price", lambda d: _set(d, [300], "low", -5.0), "integrity"),
    ("one_bad_tick_spikes", _spikes, "quality"),
    ("frozen_prices", _frozen, "quality"),
    ("split_not_adjusted", _split, "quality"),
    ("outage_gap", _outage, "quality"),
    ("sparse_missing_bars", _sparse_gaps, "quality"),
    ("zero_volume_rows", _zero_volume, "quality"),
    ("stale_repeated_bars", _stale_repeat, "quality"),
    ("price_jump_x10", _jump, "quality"),
]

# Defects the data checks are known to miss; a new miss fails the run, and so does a gap that closed.
KNOWN_GAPS: dict[str, str] = {
    f"{name}/{freq}": reason
    for name, reason in (
        ("sparse_missing_bars", "isolated missing bars (2.5 % of rows) are below the gap rule: the step must exceed 1.5 x the 95th percentile step"),
        ("stale_repeated_bars", "a run of 40 repeated bars (1.6-2.7 % of the table) is below the frozen-share threshold"),
    )
    for freq in FREQS
}


def _flag(df: pd.DataFrame) -> dict[str, bool]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            report = verify_strategy(df, signal_fn=_sma)
        except ValueError:
            return {"integrity": True, "quality": False, "refused": True}
    status = {c["id"]: c["status"] for c in report["checks"]}
    return {"integrity": status.get("data_integrity") == "fail", "quality": status.get("data_quality") in ("warn", "fail"), "refused": False}


@pytest.mark.parametrize("freq", FREQS)
@pytest.mark.parametrize("name, make, family", DEFECTS, ids=[d[0] for d in DEFECTS])
def test_defect_is_flagged(name: str, make: object, family: str, freq: str) -> None:
    flags = _flag(make(clean(freq)))
    flagged = flags["integrity"] or flags["quality"]
    key = f"{name}/{freq}"
    if key in KNOWN_GAPS:
        assert not flagged, f"{key} is now flagged: remove it from KNOWN_GAPS"
    else:
        assert flagged, f"{key} was not flagged by a data check ({flags})"


@pytest.mark.parametrize("freq", FREQS)
@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_clean_tables_are_not_flagged(freq: str, seed: int) -> None:
    flags = _flag(clean(freq, seed))
    assert not flags["integrity"] and not flags["quality"], flags
