"""Reference pairs strategy with a rolling hedge ratio, booked two ways: the wrong way and the tradable way.

A pairs backtest holds one unit of leg ``y`` against ``-beta`` units of leg ``x`` and trades the z-score of the
spread ``s = y - beta * x - alpha``. When ``(alpha, beta)`` are re-estimated on a rolling window, booking the P&L as
``position * (s_t - s_{t-1})`` includes the change of the hedge itself, ``-(d_beta * x_t + d_alpha)``, which nobody can
earn. This module is the small, numpy-only model used by the demo, the null test, the tests and the examples; the
formulas are those of the paper "Phantom Mean Reversion".
"""

from __future__ import annotations

import numpy as np

DEFAULT_WINDOW = 100


def rolling_ols(y: np.ndarray, x: np.ndarray, w: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """OLS ``y = a + b x`` over the trailing window ``[t-w+1, t]`` (inclusive, no look-ahead).

    Args:
        y: Log prices of the dependent leg, shape ``(paths, bars)``.
        x: Log prices of the hedge leg, same shape.
        w: Window length in bars (at least 3).

    Returns:
        ``(alpha, beta, residual_sd)``, each of shape ``(paths, bars)``; NaN before the first full window.
    """
    if w < 3:
        raise ValueError("the window needs at least 3 bars")

    def rsum(a: np.ndarray) -> np.ndarray:
        c = np.cumsum(a, axis=1)
        out = np.full_like(a, np.nan)
        out[:, w - 1] = c[:, w - 1]
        out[:, w:] = c[:, w:] - c[:, :-w]
        return out

    sx, sy = rsum(x), rsum(y)
    sxx, sxy, syy = rsum(x * x), rsum(x * y), rsum(y * y)
    with np.errstate(divide="ignore", invalid="ignore"):
        b = (sxy - sx * sy / w) / (sxx - sx * sx / w)
    a = (sy - b * sx) / w
    rss = syy - sy * sy / w - b * (sxy - sx * sy / w)
    sd = np.sqrt(np.maximum(rss / (w - 2), 1e-18))
    return a, b, sd


def positions(z: np.ndarray, entry: float = 2.0, exit_: float = 0.5) -> np.ndarray:
    """Z-score state machine per path: short the spread above ``entry``, long below ``-entry``, flat inside ``exit_``."""
    paths, bars = z.shape
    pos = np.zeros((paths, bars))
    cur = np.zeros(paths)
    for t in range(bars):
        zt = z[:, t]
        ok = np.isfinite(zt)
        cur = np.where(ok & (cur == 0) & (zt > entry), -1.0, cur)
        cur = np.where(ok & (cur == 0) & (zt < -entry), 1.0, cur)
        cur = np.where(ok & (cur != 0) & (np.abs(zt) < exit_), 0.0, cur)
        cur = np.where(ok, cur, 0.0)
        pos[:, t] = cur
    return pos


def pair_pnl(log_y: np.ndarray, log_x: np.ndarray, w: int = DEFAULT_WINDOW, *, booking: str = "spread_change") -> dict[str, np.ndarray]:
    """P&L per bar of the z-score pairs rule on one pair, booked as ``spread_change`` (wrong) and as ``legs`` (tradable).

    Args:
        log_y: Log prices of leg y, shape ``(bars,)``.
        log_x: Log prices of leg x.
        w: Rolling window of the hedge fit.
        booking: Only used to name the primary series returned under ``"pnl"``: ``"spread_change"`` or ``"legs"``.

    Returns:
        Arrays of length ``bars`` (zero before the first full window): ``booked`` (position times the change of the
        re-estimated spread), ``tradable`` (what the held legs earn), ``phantom`` (their difference), ``qty_y`` and
        ``qty_x`` (quantities held over each bar, in log-notional units) and ``pnl`` (the series picked by ``booking``).
    """
    if booking not in ("spread_change", "legs"):
        raise ValueError("booking must be 'spread_change' or 'legs'")
    y, x = np.asarray(log_y, dtype=np.float64)[None, :], np.asarray(log_x, dtype=np.float64)[None, :]
    a, b, sd = rolling_ols(y, x, w)
    s = y - b * x - a
    pos = positions(s / sd)[0]
    a, b, s, y, x = a[0], b[0], s[0], y[0], x[0]
    n = y.size
    q = np.zeros(n)
    q[1:] = pos[:-1]  # decided at t-1, held over the bar ending at t
    b_prev = np.zeros(n)
    b_prev[1:] = b[:-1]
    ds, dy, dx = np.zeros(n), np.zeros(n), np.zeros(n)
    ds[1:], dy[1:], dx[1:] = np.diff(s), np.diff(y), np.diff(x)
    booked = np.nan_to_num(q * ds)
    tradable = np.nan_to_num(q * (dy - b_prev * dx))
    booked[: w + 1] = 0.0
    tradable[: w + 1] = 0.0
    qty_x = -q * np.nan_to_num(b_prev)
    return {
        "booked": booked, "tradable": tradable, "phantom": booked - tradable,
        "qty_y": q, "qty_x": qty_x, "pnl": booked if booking == "spread_change" else tradable,
    }


def random_walk(bars: int, vol: float, rng: np.random.Generator) -> np.ndarray:
    """A Gaussian random walk of log prices with per-bar standard deviation ``vol``."""
    return np.cumsum(vol * rng.standard_normal(bars))


def random_walk_pair(bars: int, vol: float, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Two independent random walks of log prices (no relationship between them by construction)."""
    return random_walk(bars, vol, rng), random_walk(bars, vol, rng)


__all__ = ["DEFAULT_WINDOW", "pair_pnl", "positions", "random_walk", "random_walk_pair", "rolling_ols"]
