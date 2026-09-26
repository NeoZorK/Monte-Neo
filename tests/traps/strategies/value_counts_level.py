"""TRAP: value_counts() over the whole series picks the busiest price level, future included."""

import numpy as np


def signal(df):
    busiest = df["close"].round(-1).value_counts().idxmax()
    return np.where(df["close"] < busiest, 1, -1)
