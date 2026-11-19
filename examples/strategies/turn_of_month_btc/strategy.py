"""Strategy Lab idea (author of the idea: Claude Sonnet 5.5; process and verification: Rostyslav Shcherbyna).

Not investment advice. Parameters are fixed BEFORE any data is looked at; see card.md.
"""

import numpy as np
import pandas as pd

META = {"kind": "verify", "asset": "spot_BTCUSDT", "title": "Turn-of-month seasonality, BTC", "family": "seasonality",
        "params": {"first": 28, "last": 3}, "grid": {"first": [27, 28, 29], "last": [2, 3, 4]}}


def signal(df: pd.DataFrame, first: int = 28, last: int = 3) -> np.ndarray:
    """Long from day `first` of a month to day `last` of the next; flat otherwise (the calendar is known in advance)."""
    day = pd.to_datetime(df["timestamp"]).dt.day
    return ((day >= first) | (day <= last)).astype(float).to_numpy()
