"""TRAP: a loop that compares each bar with the next one."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    out = np.zeros(len(close))
    for i in range(len(close) - 1):
        out[i] = 1.0 if close[i + 1] > close[i] else -1.0
    return out
