"""Strategy Lab idea.

Not investment advice. Parameters are fixed BEFORE any data is looked at; see card.md.
"""

import numpy as np
import pandas as pd

META = {"kind": "verify", "asset": "spot_ETHUSDT", "title": "SMA trend filter, ETH", "family": "trend",
        "params": {"window": 100}, "grid": {"window": [50, 100, 150, 200]}}


def signal(df: pd.DataFrame, window: int = 100) -> np.ndarray:
    """Long while the close is above its simple moving average, flat below."""
    sma = df["close"].rolling(window).mean()
    return (df["close"] > sma).astype(float).to_numpy()
