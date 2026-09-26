"""TRAP: mode() of rounded prices is the most frequent level over the whole dataset."""

import numpy as np


def signal(df):
    level = df["close"].round(-1).mode().iloc[0]
    return np.where(df["close"] < level, 1, -1)
