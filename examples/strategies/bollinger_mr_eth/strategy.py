"""Strategy Lab idea (author of the idea: Claude Sonnet 5.5; process and verification: Rostyslav Shcherbyna).

Not investment advice. Parameters are fixed BEFORE any data is looked at; see card.md.
"""

import numpy as np
import pandas as pd

META = {"kind": "verify", "asset": "spot_ETHUSDT", "title": "Bollinger band reversion, ETH", "family": "mean_reversion",
        "params": {"window": 20, "k": 2.0}, "grid": {"window": [20, 40], "k": [1.5, 2.0, 2.5]}}


def signal(df: pd.DataFrame, window: int = 20, k: float = 2.0) -> np.ndarray:
    """Buy a close below the lower band; hold until the close returns to the middle band."""
    close = df["close"]
    mid = close.rolling(window).mean()
    sd = close.rolling(window).std()
    enter = close < mid - k * sd
    leave = close >= mid
    state = pd.Series(np.nan, index=df.index)
    state[enter] = 1.0
    state[leave & ~enter] = 0.0
    return state.ffill().fillna(0.0).to_numpy()
