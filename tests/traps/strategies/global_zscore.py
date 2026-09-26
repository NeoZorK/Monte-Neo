"""TRAP: z-score against whole-series mean/std (future statistics)."""

import numpy as np


def signal(df):
    close = df["close"]
    z = (close - close.mean()) / close.std()
    return np.where(z < 0.0, 1, 0)
