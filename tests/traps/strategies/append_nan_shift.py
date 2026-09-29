"""TRAP: the next close is obtained by slicing and appending NaN, a shift(-1) written without shift()."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    nxt = np.append(close[1:], np.nan)
    return np.where(nxt > close, 1, 0)
