"""Data quality: errors in otherwise well-formed OHLCV that create fake profits.

``data_integrity`` rejects broken rows (NaN, high < low, out-of-order time). The data
here is valid but suspicious, so every finding is a warning, with one exception: when
most of a strategy's profit comes from one-bar spikes, the profit is a data error.

* **Spikes:** a close-to-close move larger than ``max(20 x robust scale, 5%)`` that the
  next bar takes back by at least 75%. Real gaps on news do not revert; bad ticks do.
* **Frozen prices:** runs of at least 5 bars where open = high = low = close = the
  previous close, when they cover more than 2% of the bars.
* **Gaps in time:** a step longer than 5 x the median step; in session markets (long
  steps every week) only a step well beyond the usual nights and weekends.
* **Split jumps:** an open-to-previous-close ratio within 3% of 2, 3, 4, 5, 10 or 20
  (or its inverse) that is far outside the normal range: an unadjusted split.
* **Zero volume:** more than 5% of bars without volume (quotes, not trades).
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.stats import timestamp_series

SPIKE_SCALE = 20.0
SPIKE_MIN_MOVE = 0.05
SPIKE_REVERT = 0.75
FROZEN_RUN = 5
FROZEN_SHARE = 0.02
GAP_FACTOR = 5.0
STALE_RUN = 20  # identical bars in a row: a feed that stopped updating
MISSING_SHARE = 0.01  # steps of 1.5-5 x the usual one, in a market without closed days
SESSION_RATE = 0.5  # long steps per week that mark a market with closed hours
SPLIT_RATIOS = (2.0, 3.0, 4.0, 5.0, 10.0, 20.0)
SPLIT_TOLERANCE = 0.03
ZERO_VOLUME_SHARE = 0.05
PROFIT_SHARE_FAIL = 0.5
MAX_LISTED = 10


def _columns(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    return arr[:, None] if arr.ndim == 1 else arr


def _scale(log_ret: np.ndarray) -> float:
    finite = log_ret[np.isfinite(log_ret)]
    if finite.size < 10:
        return 0.0
    return float(1.4826 * np.median(np.abs(finite - np.median(finite))))


def spikes(close: np.ndarray) -> np.ndarray:
    """Boolean mask ``(bars, instruments)`` of bars whose move the next bar takes back."""
    c = _columns(close)
    out = np.zeros(c.shape, dtype=bool)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.diff(np.log(c), axis=0)  # r[t - 1] = move into bar t
    for s in range(c.shape[1]):
        col = r[:, s]
        limit = max(SPIKE_SCALE * _scale(col), SPIKE_MIN_MOVE)
        move, back = col[:-1], col[1:]
        with np.errstate(invalid="ignore"):
            hit = (np.abs(move) > limit) & (np.sign(back) == -np.sign(move)) & (np.abs(move + back) <= (1 - SPIKE_REVERT) * np.abs(move))
        out[1:-1, s] = np.nan_to_num(hit, nan=0.0).astype(bool)
    return out


def frozen_bars(ohlc: dict[str, np.ndarray]) -> np.ndarray:
    """Mask of bars inside runs of at least ``FROZEN_RUN`` bars with no price change at all."""
    o, h, l, c = (_columns(ohlc[k]) for k in ("open", "high", "low", "close"))
    flat = np.zeros(c.shape, dtype=bool)
    flat[1:] = (o[1:] == c[:-1]) & (h[1:] == c[:-1]) & (l[1:] == c[:-1]) & (c[1:] == c[:-1])
    # Length of the flat run ending at each bar (cumulative count reset at every non-flat bar).
    count = np.cumsum(flat, axis=0)
    reset = np.maximum.accumulate(np.where(flat, 0, count), axis=0)
    run = count - reset
    # A bar is frozen when the run through it reaches FROZEN_RUN: walk back from run ends.
    ends = flat & (run >= FROZEN_RUN)
    ends[:-1] &= ~flat[1:]
    out = np.zeros_like(flat)
    for t, s in zip(*np.nonzero(ends), strict=True):
        out[t - run[t, s] + 1 : t + 1, s] = True
    return out


def split_jumps(ohlc: dict[str, np.ndarray]) -> list[tuple[int, int, float]]:
    """(bar, instrument, ratio) where the open jumps by a split-like ratio from the previous close."""
    o, c = _columns(ohlc["open"]), _columns(ohlc["close"])
    found = []
    with np.errstate(divide="ignore", invalid="ignore"):
        # The jump shows at the open (split between sessions) or, when the vendor keeps
        # the old open, in the close.
        ratios = (o[1:] / c[:-1], c[1:] / c[:-1])
        normal = np.diff(np.log(c), axis=0)
    for s in range(c.shape[1]):
        limit = max(SPIKE_SCALE * _scale(normal[:, s]), SPIKE_MIN_MOVE)
        seen: set[int] = set()
        for ratio in ratios:
            with np.errstate(divide="ignore", invalid="ignore"):
                far = np.isfinite(ratio[:, s]) & (np.abs(np.log(ratio[:, s])) > limit)
            for t in np.flatnonzero(far):
                x = float(ratio[t, s])
                if t in seen:
                    continue
                if any(abs(x * k - 1.0) <= SPLIT_TOLERANCE or abs(x / k - 1.0) <= SPLIT_TOLERANCE for k in SPLIT_RATIOS):
                    seen.add(int(t))
                    found.append((int(t + 1), s, x))
    return sorted(found)


def stale_run(ohlc: dict[str, np.ndarray]) -> int:
    """Longest run of bars identical to the one before them (open, high, low and close all equal)."""
    best = 0
    cols = [_columns(ohlc[k]) for k in ("open", "high", "low", "close")]
    same = np.ones((cols[0].shape[0] - 1, cols[0].shape[1]), dtype=bool) if cols[0].shape[0] > 1 else np.zeros((0, cols[0].shape[1]), dtype=bool)
    for c in cols:
        same &= np.nan_to_num(c[1:] == c[:-1], nan=0.0).astype(bool)
    for s in range(same.shape[1]):
        run = 0
        for hit in same[:, s]:
            run = run + 1 if hit else 0
            best = max(best, run)
    return best


def time_gaps(timestamps: Any) -> dict[str, Any]:
    """Steps in time that are missing data rather than a closed market.

    A long step is one over ``GAP_FACTOR`` x the median step. When long steps recur at
    least every other week (nights and weekends of a market with closed hours), only a
    step over 1.5 x their 95th percentile is a gap; otherwise (24/7 markets, daily bars)
    every long step is one.
    """
    empty = {"count": 0, "largest_hours": None, "missing_share": 0.0}
    if timestamps is None:
        return empty
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parsed = pd.to_datetime(timestamp_series(timestamps), utc=True, errors="coerce").dropna()
    ns = parsed.to_numpy(dtype="datetime64[ns]").astype(np.int64)
    steps = np.diff(ns).astype(np.float64)
    steps = steps[steps > 0]
    if steps.size < 20:
        return empty
    median = float(np.median(steps))
    long = steps[steps > GAP_FACTOR * median]
    weeks = (ns[-1] - ns[0]) / 6.048e14
    closed_days = int(np.count_nonzero((steps > 2.5 * median) & (steps <= GAP_FACTOR * median)))  # a daily table with weekends
    sessions = long.size >= max(SESSION_RATE * weeks, 3)
    if sessions:
        big = long[long > 1.5 * float(np.percentile(long, 95))]
    else:
        big = long
    missing = 0.0
    if not sessions and closed_days < max(SESSION_RATE * weeks, 3):
        # A market that never closes: a step of two or three bars is a bar (or two) that is missing.
        missing = float(np.count_nonzero((steps > 1.5 * median) & (steps <= GAP_FACTOR * median)) / steps.size)
    return {"count": int(big.size), "largest_hours": float(big.max() / 3.6e12) if big.size else None, "missing_share": missing}


def data_quality(ohlc: dict[str, np.ndarray], timestamps: Any = None, volume: Any = None) -> dict[str, Any]:
    """All quality findings for one instrument ``(bars,)`` or a universe ``(bars, instruments)``."""
    spike_mask = spikes(ohlc["close"])
    frozen = frozen_bars(ohlc)
    valid = np.isfinite(_columns(ohlc["close"]))
    frozen_share = float(frozen.sum() / max(valid.sum(), 1))
    splits = split_jumps(ohlc)
    gaps = time_gaps(timestamps)
    stale = stale_run(ohlc)
    zero_share = None
    if volume is not None:
        vol = np.asarray(volume, dtype=np.float64)
        vol = vol[np.isfinite(vol)]
        zero_share = float(np.mean(vol <= 0.0)) if vol.size else None
    spike_bars, spike_cols = np.nonzero(spike_mask)
    return {
        "spike_mask": spike_mask,
        "spikes": int(spike_mask.sum()),
        "spike_examples": [{"bar": int(t), "instrument": int(s)} for t, s in zip(spike_bars[:MAX_LISTED], spike_cols[:MAX_LISTED], strict=True)],
        "frozen_bars": int(frozen.sum()),
        "frozen_share": frozen_share,
        "split_jumps": len(splits),
        "split_examples": [{"bar": t, "instrument": s, "ratio": round(x, 4)} for t, s, x in splits[:MAX_LISTED]],
        "stale_run": stale,
        "missing_share": gaps["missing_share"],
        "time_gaps": gaps["count"],
        "largest_gap_hours": gaps["largest_hours"],
        "zero_volume_share": zero_share,
    }


def spike_profit_share(equity: np.ndarray, spike_mask: np.ndarray, traded: np.ndarray | None = None) -> float | None:
    """Share of the strategy's log profit earned on spike bars and the bars that revert them.

    With ``traded`` (positions, same shape as the mask) only spikes in instruments the
    strategy held around the spike count: a bad tick in a symbol it never traded is harmless.
    """
    eq = np.asarray(equity, dtype=np.float64)
    cells = np.asarray(spike_mask, dtype=bool)
    cells = cells[:, None] if cells.ndim == 1 else cells
    if traded is not None:
        held = np.asarray(traded, dtype=np.float64)
        held = (held[:, None] if held.ndim == 1 else held) != 0
        near = held.copy()
        near[1:] |= held[:-1]
        near[:-1] |= held[1:]
        cells = cells & near
    mask = cells.any(axis=1)
    if eq.size < 3 or not mask.any():
        return None
    with np.errstate(divide="ignore", invalid="ignore"):
        step = np.log(eq[1:] / eq[:-1])  # step[t - 1]: equity change into bar t
    step = np.nan_to_num(step, nan=0.0, posinf=0.0, neginf=0.0)
    total = float(step.sum())
    if total <= 0.0:
        return None
    touched = mask.copy()
    touched[1:] |= mask[:-1]  # the reverting bar
    touched[2:] |= mask[:-2]  # fills at the next open reach one bar further
    return float(step[touched[1:]].sum() / total)


def quality_row(quality: dict[str, Any], profit_share: float | None, symbols: list[str] | None = None) -> dict[str, Any]:
    """The ``data_quality`` check row."""
    from monte_neo.verify.checks import check

    details = {k: v for k, v in quality.items() if k != "spike_mask"}
    details["spike_profit_share"] = profit_share
    if symbols:
        for item in details["spike_examples"] + details["split_examples"]:
            item["symbol"] = symbols[item["instrument"]]
    found = []
    if quality["spikes"]:
        found.append(f"{quality['spikes']} one-bar price spike{'s' if quality['spikes'] > 1 else ''}")
    if quality["frozen_share"] > FROZEN_SHARE:
        found.append(f"{quality['frozen_share']:.0%} of bars frozen")
    if quality["stale_run"] >= STALE_RUN:
        found.append(f"{quality['stale_run']} identical bars in a row (a feed that stopped updating)")
    if quality["missing_share"] >= MISSING_SHARE:
        found.append(f"{quality['missing_share']:.1%} of the steps skip a bar")
    if quality["split_jumps"]:
        found.append(f"{quality['split_jumps']} split-like jump{'s' if quality['split_jumps'] > 1 else ''}")
    if quality["time_gaps"]:
        found.append(f"{quality['time_gaps']} gap{'s' if quality['time_gaps'] > 1 else ''} in time")
    if quality["zero_volume_share"] is not None and quality["zero_volume_share"] > ZERO_VOLUME_SHARE:
        found.append(f"{quality['zero_volume_share']:.0%} of bars without volume")
    if profit_share is not None and profit_share > PROFIT_SHARE_FAIL and quality["spikes"]:
        summary = f"{min(profit_share, 1.0):.0%} of the profit comes from {quality['spikes']} one-bar price spikes (bad ticks)"
        return check("data_quality", "integrity", "fail", summary, details)
    if found:
        return check("data_quality", "integrity", "warn", "suspicious data: " + ", ".join(found), details)
    return check("data_quality", "integrity", "pass", "no spikes, frozen prices, split jumps or gaps", details)


__all__ = ["data_quality", "frozen_bars", "quality_row", "spike_profit_share", "spikes", "split_jumps", "time_gaps"]
