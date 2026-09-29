"""Datasets for the verifier trap suite (importable from tests outside this folder)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def planted_momentum_ohlcv(n: int = 5000, phi: float = 0.15, sigma: float = 0.005, seed: int = 7) -> pd.DataFrame:
    """Hourly bars whose returns follow AR(1) with ``phi`` > 0 (a real, causal edge)."""
    rng = np.random.default_rng(seed)
    eps = rng.normal(0.0, sigma, n)
    rets = np.zeros(n)
    for i in range(1, n):
        rets[i] = phi * rets[i - 1] + eps[i]
    close = 100.0 * np.exp(np.cumsum(rets))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    wiggle = rng.uniform(0.0001, 0.001, n)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC"),
            "open": open_,
            "high": np.maximum(open_, close) * (1.0 + wiggle),
            "low": np.minimum(open_, close) * (1.0 - wiggle),
            "close": close,
        }
    )


def universe_ohlcv(n: int = 700, symbols: int = 6, seed: int = 11, delist: bool = True) -> pd.DataFrame:
    """Daily bars for several random-walk symbols: one listed late and (optionally) one delisted."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2019-01-01", periods=n)
    frames = []
    for k in range(symbols):
        start = n // 4 if k == 1 else 0
        end = 2 * n // 3 if (delist and k == 2) else n
        close = 40.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.015, end - start)))
        open_ = np.roll(close, 1)
        open_[0] = close[0]
        frames.append(
            pd.DataFrame(
                {
                    "timestamp": days[start:end], "symbol": f"S{k}", "open": open_,
                    "high": np.maximum(open_, close) * 1.003, "low": np.minimum(open_, close) * 0.997, "close": close,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)
