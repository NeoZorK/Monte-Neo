"""HONEST: SMA crossover computed in a loop from trailing slices c[i - 10:i + 1]."""

import numpy as np


def signal(df):
    c = df["close"].to_numpy()
    out = np.zeros(len(c))
    for i in range(50, len(c)):
        out[i] = 1 if c[i - 10 : i + 1].mean() > c[i - 50 : i + 1].mean() else 0
    return out
