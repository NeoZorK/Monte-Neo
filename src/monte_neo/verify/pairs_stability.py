"""Is the pair's relationship stable over time? Rolling hedge ratio and rolling Engle-Granger cointegration.

A pair that is cointegrated over the whole sample can still be untradable: the hedge ratio may wander, or the link may
hold only in part of the history. Both are visible in windows that slide over the sample. The window statistics are
descriptive, not a joint test: with overlapping windows, "share of windows that reject" is a diagnostic, not a p-value.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.verify.pairs_unitroot import engle_granger

MIN_WINDOW = 60


def default_window(n: int) -> int:
    """A quarter of the sample, but at least 250 bars (and never more than half)."""
    return int(min(max(250, n // 4), n // 2))


def _starts(n: int, window: int, step: int | None) -> np.ndarray:
    hop = step or max(1, window // 4)
    return np.arange(0, n - window + 1, hop)


def rolling_hedge_ratio(log_y: np.ndarray, log_x: np.ndarray, window: int | None = None, step: int | None = None) -> dict[str, Any]:
    """Hedge ratio ``beta`` of ``y = a + b x`` in sliding windows.

    Returns:
        ``starts`` (window start indices), ``beta`` per window, ``cv`` (std / |median| of the betas), ``drift`` (last
        minus first window beta over |median|) and ``window``.
    """
    y, x = np.asarray(log_y, dtype=np.float64), np.asarray(log_x, dtype=np.float64)
    w = default_window(y.size) if window is None else int(window)
    if w < MIN_WINDOW or w > y.size:
        raise ValueError(f"window must be between {MIN_WINDOW} and the number of bars")
    starts = _starts(y.size, w, step)
    beta = np.empty(starts.size)
    for i, s in enumerate(starts):
        xs, ys = x[s : s + w], y[s : s + w]
        xc = xs - xs.mean()
        denom = float(xc @ xc)
        beta[i] = float(xc @ (ys - ys.mean())) / denom if denom > 0 else np.nan
    med = float(np.nanmedian(beta))
    scale = max(abs(med), 1e-12)
    return {
        "starts": starts, "beta": beta, "window": w, "median": med,
        "cv": float(np.nanstd(beta) / scale), "drift": float((beta[-1] - beta[0]) / scale),
    }


def rolling_cointegration(log_y: np.ndarray, log_x: np.ndarray, window: int | None = None, step: int | None = None) -> dict[str, Any]:
    """Engle-Granger test in sliding windows.

    Returns:
        ``starts``, ``stat`` per window, ``reject5`` (bool per window), ``share`` of windows that reject at 5 %,
        ``last_reject_end`` (end index of the last rejecting window, or -1) and ``window``.
    """
    y, x = np.asarray(log_y, dtype=np.float64), np.asarray(log_x, dtype=np.float64)
    w = default_window(y.size) if window is None else int(window)
    if w < MIN_WINDOW or w > y.size:
        raise ValueError(f"window must be between {MIN_WINDOW} and the number of bars")
    starts = _starts(y.size, w, step)
    runs = [engle_granger(y[s : s + w], x[s : s + w]) for s in starts]
    stat = np.array([r["stat"] for r in runs])
    reject = np.array([r["reject"][0.05] for r in runs])
    hits = np.flatnonzero(reject)
    return {
        "starts": starts, "stat": stat, "reject5": reject, "share": float(reject.mean()), "window": w,
        "last_reject_end": int(starts[hits[-1]] + w - 1) if hits.size else -1,
    }


__all__ = ["MIN_WINDOW", "default_window", "rolling_cointegration", "rolling_hedge_ratio"]
