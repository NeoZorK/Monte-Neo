"""Strategy Lab idea (author of the idea: Claude Sonnet 5.5; process and verification: Rostyslav Shcherbyna).

Not investment advice. Parameters are fixed BEFORE any data is looked at; see card.md.
"""

import numpy as np
import pandas as pd

META = {"kind": "verify", "asset": "spot_BTCUSDT", "title": "RSI(2) mean reversion in an uptrend, BTC", "family": "mean_reversion",
        "params": {"rsi_len": 2, "buy": 10, "sell": 70, "trend": 200}, "grid": {"buy": [5, 10, 15], "sell": [60, 70]}}


def signal(df: pd.DataFrame, rsi_len: int = 2, buy: float = 10, sell: float = 70, trend: int = 200) -> np.ndarray:
    """Buy a short-term oversold dip (RSI below `buy`) only while the close is above its `trend`-bar average; exit when RSI passes `sell`."""
    close = df["close"]
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / rsi_len, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / rsi_len, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    enter = (rsi < buy) & (close > close.rolling(trend).mean())
    leave = rsi > sell
    state = pd.Series(np.nan, index=df.index)
    state[enter] = 1.0
    state[leave & ~enter] = 0.0
    return state.ffill().fillna(0.0).to_numpy()
