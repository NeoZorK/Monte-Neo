"""Synthetic universes for the trend_v1 demo: trends, random walks and a choppy market.

Run: python make_data.py [output_dir]

Writes ``trends.csv``, ``random.csv`` and ``choppy.csv`` (long format: timestamp, symbol, open, high, low,
close, volume). The files are not committed; generate them here. All data are synthetic and seeded.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

N_SYMBOLS = 12
YEARS = 12
SEED = 20260101
DAILY_VOL = 0.01  # about 16 % a year


def _frame(log_returns: np.ndarray, rng: np.random.Generator, start: str = "2010-01-01") -> pd.DataFrame:
    """Long OHLCV table from daily log returns of shape (bars, symbols)."""
    n_bars, n_sym = log_returns.shape
    stamps = pd.bdate_range(start, periods=n_bars)
    close = 100.0 * np.exp(np.cumsum(log_returns, axis=0))
    prev = np.vstack([np.full((1, n_sym), 100.0), close[:-1]])
    open_ = prev * np.exp(rng.normal(0.0, DAILY_VOL * 0.1, size=close.shape))
    spread = np.abs(rng.normal(0.0, DAILY_VOL * 0.5, size=close.shape))
    high = np.maximum(open_, close) * np.exp(spread)
    low = np.minimum(open_, close) * np.exp(-spread)
    out = pd.DataFrame(
        {
            "timestamp": np.repeat(stamps.strftime("%Y-%m-%d"), n_sym),
            "symbol": np.tile([f"S{i:02d}" for i in range(n_sym)], n_bars),
            "open": open_.ravel(),
            "high": high.ravel(),
            "low": low.ravel(),
            "close": close.ravel(),
            "volume": np.full(close.size, 1_000_000.0),
        }
    )
    return out


def _noise(n_bars: int, n_sym: int, rng: np.random.Generator) -> np.ndarray:
    """Daily shocks with a mild common factor (cross-correlation about 0.1)."""
    common = rng.normal(0.0, DAILY_VOL, size=(n_bars, 1))
    own = rng.normal(0.0, DAILY_VOL, size=(n_bars, n_sym))
    return np.sqrt(0.1) * common + np.sqrt(0.9) * own


def trends(n_symbols: int = N_SYMBOLS, years: int = YEARS, seed: int = SEED) -> pd.DataFrame:
    """Planted, slowly switching trends: each symbol's drift is up, down or flat for months at a time."""
    rng = np.random.default_rng(seed)
    n_bars = years * 252
    drift = np.zeros((n_bars, n_symbols))
    for s in range(n_symbols):
        t = 0
        while t < n_bars:
            length = int(rng.integers(120, 400))  # persists for 6 to 19 months
            level = rng.choice([-1.0, 0.0, 1.0], p=[0.35, 0.2, 0.45])
            drift[t : t + length, s] = level * 0.0004  # about 10 % a year in a trend
            t += length
    return _frame(drift + _noise(n_bars, n_symbols, rng), rng)


def random_walks(n_symbols: int = N_SYMBOLS, years: int = YEARS, seed: int = SEED + 1) -> pd.DataFrame:
    """The same instruments as pure random walks: no drift, no memory."""
    rng = np.random.default_rng(seed)
    n_bars = years * 252
    return _frame(_noise(n_bars, n_symbols, rng), rng)


def choppy(n_symbols: int = N_SYMBOLS, years: int = YEARS, seed: int = SEED + 2, phi: float = -0.25) -> pd.DataFrame:
    """A mean-reverting market: AR(1) with negative coefficient on returns, so moves tend to reverse."""
    rng = np.random.default_rng(seed)
    n_bars = years * 252
    shocks = _noise(n_bars, n_symbols, rng)
    ret = np.zeros_like(shocks)
    for t in range(1, n_bars):
        ret[t] = phi * ret[t - 1] + shocks[t]
    return _frame(ret, rng)


def main() -> None:
    """Write the three CSV files into the given folder (default: the current one)."""
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    out.mkdir(parents=True, exist_ok=True)
    for name, frame in (("trends", trends()), ("random", random_walks()), ("choppy", choppy())):
        frame.to_csv(out / f"{name}.csv", index=False)
        print(f"{out / (name + '.csv')}: {len(frame)} rows, {frame['symbol'].nunique()} symbols")


if __name__ == "__main__":
    main()
