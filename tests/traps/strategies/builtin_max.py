"""TRAP: Python's built-in max() over the whole column includes future bars."""

import numpy as np


def signal(df):
    top = max(df["close"])
    return np.where(df["close"] > top * 0.995, -1, 1)
