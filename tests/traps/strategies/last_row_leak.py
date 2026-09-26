"""TRAP: every bar is compared with the final close of the whole dataset (.iloc[-1])."""

import numpy as np


def signal(df):
    final = df["close"].iloc[-1]
    return np.where(df["close"] < final, 1, -1)
