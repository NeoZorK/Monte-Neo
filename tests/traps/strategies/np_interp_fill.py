"""TRAP: np.interp fills gaps between sparse points with a line to the next known point."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    idx = np.arange(len(close))
    sparse = idx[::30]
    line = np.interp(idx, sparse, close[sparse])
    return np.where(line > close, 1, -1)
