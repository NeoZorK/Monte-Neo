"""HONEST: rolling mean with min_periods=1 (short windows at the start, still past-only)."""

import numpy as np


def signal(df):
    mean = df["close"].rolling(50, min_periods=1).mean()
    return np.where(df["close"] > mean, 1, 0)
