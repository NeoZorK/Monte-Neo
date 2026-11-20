"""Strategy Lab idea (author of the idea: Claude Sonnet 5.5; process and verification: Rostyslav Shcherbyna).

Not investment advice. Parameters are fixed BEFORE any data is looked at; see card.md.
"""

import numpy as np
import pandas as pd

META = {"kind": "verify", "asset": "spot_BTCUSDT", "title": "Volatility-targeted trend, BTC", "family": "vol_target",
        "params": {"window": 100, "target": 0.40, "vol_len": 30}, "grid": {"window": [50, 100, 200], "target": [0.3, 0.4, 0.5]}}


def signal(df: pd.DataFrame, window: int = 100, target: float = 0.40, vol_len: int = 30) -> np.ndarray:
    """SMA trend filter sized so that the expected annual volatility is `target` (weight capped at 1, no leverage)."""
    close = df["close"]
    vol = close.pct_change().rolling(vol_len).std() * np.sqrt(365)
    weight = (target / vol).clip(upper=1.0)
    trend = close > close.rolling(window).mean()
    return (weight * trend).fillna(0.0).to_numpy()
