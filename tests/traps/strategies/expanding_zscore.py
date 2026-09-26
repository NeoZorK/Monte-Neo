"""HONEST: z-score against expanding (past-only) mean and std."""

import numpy as np


def signal(df):
    close = df["close"]
    z = (close - close.expanding(50).mean()) / close.expanding(50).std()
    return np.where(z < -1.0, 1, 0)
