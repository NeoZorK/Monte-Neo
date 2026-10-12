"""Causal position transforms used by ``monte-neo repair``.

Every function takes the positions a strategy returned (one value per row of ``df``) and the same ``df``, and returns new
positions. Each one uses only rows up to the current one, per symbol when ``df`` is a universe (rows sorted by
timestamp, then symbol). The repaired strategy file embeds the source of the functions it uses, so it runs without
Monte-Neo installed; keep them self-contained (numpy and pandas only, no imports from this package).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _mn_groups(df: pd.DataFrame) -> list[np.ndarray]:
    """Row indices per symbol in time order (one group for a single instrument)."""
    if "symbol" not in df.columns:
        return [np.arange(len(df))]
    return [np.asarray(ix) for ix in df.groupby("symbol", sort=False).indices.values()]


def _mn_smooth(pos: np.ndarray, df: pd.DataFrame, span: int) -> np.ndarray:
    """Exponential moving average of the positions (fewer, smaller trades)."""
    out = np.asarray(pos, dtype=float).copy()
    for ix in _mn_groups(df):
        out[ix] = pd.Series(out[ix]).ewm(span=span, adjust=False).mean().to_numpy()
    return out


def _mn_hold(pos: np.ndarray, df: pd.DataFrame, bars: int) -> np.ndarray:
    """Keep each new position for at least ``bars`` bars."""
    src = np.asarray(pos, dtype=float)
    out = src.copy()
    for ix in _mn_groups(df):
        held, age = 0.0, bars
        for i in ix:
            if src[i] != held and age >= bars:
                held, age = src[i], 0
            out[i] = held
            age += 1
    return out


def _mn_band(pos: np.ndarray, df: pd.DataFrame, band: float) -> np.ndarray:
    """No-trade zone: move to the new target only when it differs from the held position by more than ``band``."""
    src = np.asarray(pos, dtype=float)
    out = src.copy()
    for ix in _mn_groups(df):
        held = 0.0
        for i in ix:
            if abs(src[i] - held) > band:
                held = src[i]
            out[i] = held
    return out


def _mn_tranche(pos: np.ndarray, df: pd.DataFrame, every: int, sleeves: int) -> np.ndarray:
    """Average of ``sleeves`` copies that rebalance every ``every`` bars at staggered offsets (no rebalance-day luck)."""
    src = np.asarray(pos, dtype=float)
    out = np.zeros_like(src)
    for ix in _mn_groups(df):
        n = len(ix)
        acc = np.zeros(n)
        for k in range(sleeves):
            offset = (k * every) // sleeves
            held = 0.0
            for j in range(n):
                if j >= offset and (j - offset) % every == 0:
                    held = src[ix[j]]
                acc[j] += held
        out[ix] = acc / sleeves
    return out


def _mn_voltarget(pos: np.ndarray, df: pd.DataFrame, annual: float, span: int) -> np.ndarray:
    """Scale positions down when trailing volatility (known before the bar) is above the target; never above 1x."""
    out = np.asarray(pos, dtype=float).copy()
    stamps = pd.to_datetime(df["timestamp"]) if "timestamp" in df.columns else None
    per_year = 252.0
    if stamps is not None and len(stamps) > 2:
        step = np.median(np.diff(stamps.drop_duplicates().to_numpy().astype("datetime64[s]").astype(np.int64)))
        per_year = 365.25 * 86400 / step if step > 0 and step < 86400 * 0.9 else 252.0
    target = annual / np.sqrt(per_year)
    for ix in _mn_groups(df):
        ret = pd.Series(df["close"].to_numpy()[ix]).pct_change()
        vol = ret.ewm(span=span, adjust=False).std().shift(1).to_numpy()
        scale = np.where(np.isfinite(vol) & (vol > 0), np.minimum(1.0, target / np.where(vol > 0, vol, 1.0)), 0.0)
        out[ix] = out[ix] * scale
    return out


def _mn_neutral(pos: np.ndarray, df: pd.DataFrame) -> np.ndarray:
    """Universe: subtract the cross-sectional mean at each timestamp (no net market exposure)."""
    out = np.asarray(pos, dtype=float).copy()
    if "symbol" not in df.columns:
        return out
    key = pd.to_datetime(df["timestamp"]).to_numpy()
    mean = pd.Series(out).groupby(key).transform("mean").to_numpy()
    return out - mean


def _mn_cap(pos: np.ndarray, df: pd.DataFrame, cap: float) -> np.ndarray:
    """Clip every position to ``[-cap, cap]``."""
    return np.clip(np.asarray(pos, dtype=float), -cap, cap)


def _mn_liquidity(pos: np.ndarray, df: pd.DataFrame, quantile: float) -> np.ndarray:
    """Universe with volume: no position in names whose trailing traded value is in the lowest ``quantile`` that bar."""
    out = np.asarray(pos, dtype=float).copy()
    if "symbol" not in df.columns or "volume" not in df.columns:
        return out
    value = (df["close"] * df["volume"]).to_numpy(dtype=float)
    trailing = np.full(len(df), np.nan)
    for ix in _mn_groups(df):
        trailing[ix] = pd.Series(value[ix]).rolling(20, min_periods=5).mean().shift(1).to_numpy()
    key = pd.to_datetime(df["timestamp"]).to_numpy()
    cut = pd.Series(trailing).groupby(key).transform(lambda s: s.quantile(quantile)).to_numpy()
    out[~(trailing > cut)] = 0.0
    return out


def _mn_delay(pos: np.ndarray, df: pd.DataFrame, bars: int) -> np.ndarray:
    """Act ``bars`` bars later: a signal is used only after the bar that produced it has closed."""
    out = np.asarray(pos, dtype=float).copy()
    for ix in _mn_groups(df):
        out[ix] = pd.Series(out[ix]).shift(bars).fillna(0.0).to_numpy()
    return out


TRANSFORMS = {
    "smooth": _mn_smooth, "hold": _mn_hold, "band": _mn_band, "tranche": _mn_tranche, "voltarget": _mn_voltarget,
    "neutral": _mn_neutral, "cap": _mn_cap, "liquidity": _mn_liquidity, "delay": _mn_delay,
}

__all__ = ["TRANSFORMS"]
