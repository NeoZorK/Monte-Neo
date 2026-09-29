"""TRAP (universe): each symbol's price ranked against its whole history, future bars included."""

import numpy as np


def signal(df):
    rank = df.groupby("symbol")["close"].rank(pct=True)
    return np.where(rank < 0.3, 1, np.where(rank > 0.7, -1, 0))
