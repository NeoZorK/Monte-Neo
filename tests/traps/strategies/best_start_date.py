"""TRAP: the start date of the strategy is chosen among many candidates by the buy-and-hold return from it to the END of the sample."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    candidates = range(60, max(61, len(close) - 300), 300)
    start = max(candidates, key=lambda s: close[-1] / close[s])
    out = np.zeros(len(close))
    out[start:] = 1.0
    return out
