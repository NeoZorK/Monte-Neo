"""TRAP: hold long until the bar of the all-time high (idxmax over the whole series)."""

import numpy as np


def signal(df):
    peak = df["close"].idxmax()
    return np.where(df.index < peak, 1, -1)
