"""Measured metrics of ``catalog-rules/1``: what a strategy does, read from its positions (and prices when given).

``positions`` is a wide table (rows: bars in time order, columns: symbols, values: signed position sizes).
``prices`` (same shape, close prices) lets the classifier compute returns, the sign correlation with past returns and
the size after a losing trade. Every metric that cannot be computed is ``None`` (not measured), never a guess.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

TREND_LOOKBACKS = (20, 60, 250)


def _runs(col: np.ndarray) -> list[tuple[int, int]]:
    """(start, end) bar index of every run of non-zero positions with the same sign."""
    out, start = [], None
    sign = np.sign(col)
    for i, s in enumerate(sign):
        if start is not None and s != sign[start]:
            out.append((start, i))
            start = None
        if start is None and s != 0:
            start = i
    if start is not None:
        out.append((start, len(sign)))
    return out


def _corr(a: np.ndarray, b: np.ndarray) -> float | None:
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 30 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return None
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def measure(
    positions: pd.DataFrame, prices: pd.DataFrame | None = None, *, bar_seconds: float = 86400.0, benchmark: pd.Series | None = None
) -> dict[str, Any]:
    """The measured metrics (section 2 of catalog-rules/1) with ``None`` for what the inputs do not allow."""
    pos = positions.astype(float).fillna(0.0)
    arr = pos.to_numpy()
    gross = np.abs(arr).sum(axis=1)
    active = gross > 0
    m: dict[str, Any] = {"bars": int(len(pos)), "symbols": int(pos.shape[1])}
    runs = [(c, s, e) for c in range(arr.shape[1]) for s, e in _runs(arr[:, c])]
    lengths = [e - s for _, s, e in runs]
    m["hold_median_seconds"] = float(np.median(lengths) * bar_seconds) if lengths else None
    m["n_assets_active"] = float(np.median((np.abs(arr) > 0).sum(axis=1)[active])) if active.any() else 0.0
    long_part, abs_part = np.clip(arr, 0, None).sum(), np.abs(arr).sum()
    m["long_share"] = float(long_part / abs_part) if abs_part > 0 else None
    m["net_exposure"] = float(np.mean(arr.sum(axis=1)[active] / gross[active])) if active.any() else None
    m.update({"beta_bench": None, "skew": None, "tail_ratio": None, "size_after_loss": None, "calendar_conc": None})
    m["sign_corr_past_ret"] = {}
    if isinstance(pos.index, pd.DatetimeIndex) and active.any():
        day = pos.index.day
        tom = (day <= 3) | (day >= pos.index.days_in_month - 1)  # turn of month window: last 2 and first 3 days
        share_tom = float(gross[tom].sum() / gross.sum())
        weekday = pd.Series(gross, index=pos.index).groupby(pos.index.dayofweek).sum()
        m["calendar_conc"] = max(share_tom, float(weekday.max() / weekday.sum()) if len(weekday) > 1 else 0.0)
    if prices is None:
        return m
    px = prices.reindex(index=pos.index, columns=pos.columns).astype(float)
    ret = px.pct_change().to_numpy()
    strat = np.nansum(np.vstack([np.zeros((1, arr.shape[1])), arr[:-1]]) * np.nan_to_num(ret), axis=1)[1:]
    if strat.size >= 30 and np.std(strat) > 0:
        m["skew"] = float(pd.Series(strat).skew())
        q95, q5 = np.quantile(strat, 0.95), np.quantile(strat, 0.05)
        m["tail_ratio"] = float(abs(q95) / abs(q5)) if q5 != 0 else None
        if benchmark is not None:
            b = benchmark.reindex(pos.index).to_numpy(dtype=float)[1:]
            ok = np.isfinite(b)
            if ok.sum() >= 30 and np.var(b[ok]) > 0:
                m["beta_bench"] = float(np.cov(strat[ok], b[ok])[0, 1] / np.var(b[ok], ddof=1))
    logp = np.log(px.to_numpy())
    for k in TREND_LOOKBACKS:
        if len(pos) <= k + 30:
            continue
        past = logp[k:] - logp[:-k]
        sgn = np.sign(arr[k:])
        mask = sgn != 0
        m["sign_corr_past_ret"][str(k)] = _corr(sgn[mask], np.sign(past[mask]))
    # size of the next trade relative to the previous one after a losing trade (grid / martingale sizing)
    ratios = []
    lr = np.vstack([np.full((1, arr.shape[1]), np.nan), np.diff(logp, axis=0)])
    for c in range(arr.shape[1]):
        trades = [(s, e) for cc, s, e in runs if cc == c]
        for (s0, e0), (s1, _e1) in zip(trades, trades[1:], strict=False):
            pnl = np.nansum(arr[s0:e0, c] * lr[s0 + 1 : e0 + 1, c]) if e0 + 1 <= len(lr) else np.nan
            if np.isfinite(pnl) and pnl < 0 and abs(arr[s0, c]) > 0:
                ratios.append(abs(arr[s1, c]) / abs(arr[s0, c]))
    m["size_after_loss"] = float(np.mean(ratios)) if len(ratios) >= 5 else None
    return m


__all__ = ["TREND_LOOKBACKS", "measure"]
