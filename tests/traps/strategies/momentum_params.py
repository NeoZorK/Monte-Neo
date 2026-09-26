"""HONEST (grid): momentum over `lookback` bars (edge exists on planted data)."""

import numpy as np


def signal(df, lookback=1):
    return np.where(df["close"].diff(lookback) > 0.0, 1, 0)
