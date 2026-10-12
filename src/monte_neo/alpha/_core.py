"""Shared numpy kernels for alpha checks: row ranks, rank IC, Newey-West, quantile legs."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rank_rows(x: np.ndarray) -> np.ndarray:
    """Average-tie ranks (1..n) along each row; NaN stays NaN."""
    return pd.DataFrame(x).rank(axis=1, method="average").to_numpy()


def ic_series(scores: np.ndarray, fwd: np.ndarray) -> np.ndarray:
    """Per-date Spearman rank correlation between scores and forward returns (NaN if < 3 pairs)."""
    ok = np.isfinite(scores) & np.isfinite(fwd)
    a = rank_rows(np.where(ok, scores, np.nan))
    b = rank_rows(np.where(ok, fwd, np.nan))
    cnt = np.maximum(ok.sum(axis=1, keepdims=True), 1)
    a = a - np.nansum(a, axis=1, keepdims=True) / cnt
    b = b - np.nansum(b, axis=1, keepdims=True) / cnt
    num = np.nansum(a * b, axis=1)
    den = np.sqrt(np.nansum(a * a, axis=1) * np.nansum(b * b, axis=1))
    with np.errstate(divide="ignore", invalid="ignore"):
        ic = num / den
    ic[(ok.sum(axis=1) < 3) | (den <= 0)] = np.nan
    return ic


def newey_west_t(x: np.ndarray, lag: int) -> tuple[float, float, float]:
    """(mean, standard error, t-stat) of a series with a Bartlett-kernel Newey-West variance."""
    v = x[np.isfinite(x)]
    n = len(v)
    if n < 3:
        return float("nan"), float("nan"), float("nan")
    m = float(v.mean())
    d = v - m
    lag = max(0, min(lag, n - 2))
    var = float(d @ d) / n
    for k in range(1, lag + 1):
        var += 2.0 * (1.0 - k / (lag + 1.0)) * float(d[k:] @ d[:-k]) / n
    se = float(np.sqrt(max(var, 0.0) / n))
    return m, se, (m / se if se > 0 else float("nan"))


def quantile_index(scores: np.ndarray, valid: np.ndarray, q: int) -> np.ndarray:
    """Quantile bucket 0..q-1 of each score within its date (NaN where not valid)."""
    s = np.where(valid, scores, np.nan)
    r = rank_rows(s)
    n = np.sum(valid, axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        idx = np.floor((r - 1.0) / n * q)
    idx = np.clip(idx, 0, q - 1)
    idx[~valid] = np.nan
    return idx


def leg_weights(qidx: np.ndarray, q: int) -> np.ndarray:
    """Long-short weights: +1/n_top on the top bucket, -1/n_bottom on the bottom bucket."""
    top = qidx == q - 1
    bot = qidx == 0
    nt = top.sum(axis=1, keepdims=True)
    nb = bot.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        w = np.where(top, 1.0 / nt, 0.0) - np.where(bot, 1.0 / nb, 0.0)
    return np.nan_to_num(w)


def sharpe(x: np.ndarray) -> float:
    """Mean / std of a series (per period, not annualised); NaN if undefined."""
    v = x[np.isfinite(x)]
    if len(v) < 3 or v.std(ddof=1) <= 0:
        return float("nan")
    return float(v.mean() / v.std(ddof=1))
