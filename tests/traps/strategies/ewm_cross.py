"""HONEST: exponential moving average crossover (causal)."""

import numpy as np


def signal(df):
    fast = df["close"].ewm(span=12, adjust=False).mean()
    slow = df["close"].ewm(span=48, adjust=False).mean()
    return np.where(fast > slow, 1, 0)
