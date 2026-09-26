"""TRAP: double argsort ranks each bar against the whole sample, future included."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    pct = np.argsort(np.argsort(close)) / len(close)
    return np.where(pct < 0.3, 1, np.where(pct > 0.7, -1, 0))
