"""Where the result comes from: buy-and-hold benchmark, periods, market regimes.

Everything here describes one finished backtest (its equity curve); nothing feeds
back into the strategy, so descriptive full-sample statistics (such as the median
volatility that splits the regimes) are fine.
"""

from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.engine import simulate
from monte_neo.verify.stats import bar_returns, sharpe_per_bar

MAX_SERIES_POINTS = 400
EQUAL_SEGMENTS = 4
_DAY = pd.Timedelta(days=1)


def _annualized(rets: np.ndarray, periods_per_year: float) -> float:
    return float(sharpe_per_bar(rets) * math.sqrt(max(periods_per_year, 1.0)))


def _compound(rets: np.ndarray) -> float:
    return float(np.prod(1.0 + rets) - 1.0) if rets.size else 0.0


def buy_and_hold(
    ohlc: dict[str, np.ndarray], model: ExecutionModel, positions: np.ndarray, periods_per_year: float
) -> dict[str, Any]:
    """Run the passive benchmark ``positions`` with the same costs and warm-up."""
    run = simulate(ohlc, positions, model)
    rets = bar_returns(run["equity"], start=model.warmup_bars)
    return {
        "equity": run["equity"],
        "total_return": float(run["total_return"]),
        "max_drawdown": float(run["max_drawdown"]),
        "sharpe_annualized": _annualized(rets, periods_per_year),
    }


def _parse_times(timestamps: Any, n: int) -> pd.DatetimeIndex | None:
    if timestamps is None:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parsed = pd.to_datetime(pd.Series(np.asarray(timestamps)), utc=True, errors="coerce")
    if parsed.isna().any() or len(parsed) != n:
        return None
    return pd.DatetimeIndex(parsed)


def _period_bounds(times: pd.DatetimeIndex | None, start: int, n: int) -> tuple[str, list[tuple[str, int, int]]]:
    """``(frequency, [(label, first_bar, last_bar), ...])`` covering bars ``start .. n-1``."""
    if times is not None:
        span = times[n - 1] - times[start]
        if span >= 3 * 365 * _DAY:
            freq, keys = "year", [str(t.year) for t in times]
        elif span >= 180 * _DAY:
            freq, keys = "quarter", [f"{t.year}-Q{(t.month - 1) // 3 + 1}" for t in times]
        elif span >= 60 * _DAY:
            freq, keys = "month", [f"{t.year}-{t.month:02d}" for t in times]
        else:
            freq, keys = "", []
        if freq:
            bounds: list[tuple[str, int, int]] = []
            first = start
            for i in range(start + 1, n + 1):
                if i == n or keys[i] != keys[first]:
                    bounds.append((keys[first], first, i - 1))
                    first = i
            return freq, bounds
    edges = np.linspace(start, n, EQUAL_SEGMENTS + 1).astype(int)
    bounds = [(f"bars {a}-{b - 1}", int(a), int(b - 1)) for a, b in zip(edges[:-1], edges[1:], strict=True) if b > a]
    return "segment", bounds


def periods(
    equity: np.ndarray,
    benchmark_equity: np.ndarray,
    traded: np.ndarray,
    timestamps: Any,
    start: int,
    periods_per_year: float,
) -> dict[str, Any]:
    """Return, Sharpe and exposure per calendar period (years, quarters or months) or per segment."""
    n = equity.size
    freq, bounds = _period_bounds(_parse_times(timestamps, n), start, n)
    active = np.abs(np.asarray(traded, dtype=np.float64))
    if active.ndim == 2:
        active = active.sum(axis=1)
    rows = []
    for label, a, b in bounds:
        # A period's return runs from the previous period's last bar to its own last bar.
        base = max(start, a - 1)
        rets = bar_returns(equity[base : b + 1])
        rows.append(
            {
                "period": label,
                "bars": b - a + 1,
                "return": float(equity[b] / equity[base] - 1.0) if equity[base] > 0 else 0.0,
                "benchmark_return": float(benchmark_equity[b] / benchmark_equity[base] - 1.0)
                if benchmark_equity[base] > 0
                else 0.0,
                "sharpe_annualized": _annualized(rets, periods_per_year),
                "exposure": float(np.mean(active[a : b + 1] != 0)),
            }
        )
    return {"frequency": freq, "periods": rows}


def regimes(equity: np.ndarray, market_close: np.ndarray, start: int, periods_per_year: float) -> dict[str, Any]:
    """Strategy results in rising / falling and calm / volatile markets.

    A bar's regime comes from the market's trailing return and volatility over the
    previous ``window`` bars, so it is known at the start of the bar.
    """
    n = equity.size
    window = max(20, n // 20)
    market = np.asarray(market_close, dtype=np.float64)
    m_ret = np.zeros(n)
    m_ret[1:] = market[1:] / market[:-1] - 1.0
    s_ret = np.zeros(n)
    s_ret[1:] = np.where(equity[:-1] > 0, equity[1:] / np.where(equity[:-1] > 0, equity[:-1], 1.0) - 1.0, 0.0)
    trailing = pd.Series(m_ret).rolling(window)
    trend = trailing.sum().shift(1).to_numpy()
    vol = trailing.std().shift(1).to_numpy()
    usable = np.arange(n) >= max(start + 1, window + 1)
    usable &= np.isfinite(trend) & np.isfinite(vol)
    if not usable.any():
        return {"window": window, "regimes": {}}
    vol_cut = float(np.median(vol[usable]))
    masks = {
        "rising": usable & (trend > 0),
        "falling": usable & (trend <= 0),
        "calm": usable & (vol <= vol_cut),
        "volatile": usable & (vol > vol_cut),
    }
    out = {}
    for name, mask in masks.items():
        out[name] = {
            "bars": int(mask.sum()),
            "share": float(mask.sum() / usable.sum()),
            "return": _compound(s_ret[mask]),
            "market_return": _compound(m_ret[mask]),
            "sharpe_annualized": _annualized(s_ret[mask], periods_per_year),
        }
    return {"window": window, "regimes": out}


def series(equity: np.ndarray, benchmark_equity: np.ndarray, timestamps: Any, start: int) -> dict[str, Any]:
    """Equity and benchmark from the end of warm-up, scaled to start at 1, at most 400 points."""
    n = equity.size
    idx = np.unique(np.linspace(start, n - 1, num=min(MAX_SERIES_POINTS, n - start)).astype(int))
    times = _parse_times(timestamps, n)

    def scaled(curve: np.ndarray) -> list[float]:
        base = curve[start] if curve[start] > 0 else 1.0
        return [round(float(v / base), 6) for v in curve[idx]]

    return {
        "bar": [int(i) for i in idx],
        "time": [times[i].isoformat() for i in idx] if times is not None else None,
        "equity": scaled(equity),
        "benchmark": scaled(benchmark_equity),
    }


__all__ = ["buy_and_hold", "periods", "regimes", "series"]
