"""Strategy Lab idea (author of the idea: Claude Sonnet 5.5; process and verification: Rostyslav Shcherbyna).

Not investment advice. Parameters are fixed BEFORE any data is looked at; see card.md.
"""

import numpy as np
import pandas as pd

META = {"kind": "verify", "asset": "spot_BTCUSDT", "title": "Time-series momentum, BTC", "family": "trend",
        "params": {"lookback": 90}, "grid": {"lookback": [60, 90, 120, 180]}}


def signal(df: pd.DataFrame, lookback: int = 90) -> np.ndarray:
    """Long when the return over the last `lookback` closes is positive, flat otherwise (known at the close)."""
    ret = df["close"] / df["close"].shift(lookback) - 1.0
    return (ret > 0).astype(float).to_numpy()
