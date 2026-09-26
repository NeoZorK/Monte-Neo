"""HONEST: breakout above a trailing rolling quantile of the previous bars."""

import numpy as np


def signal(df):
    upper = df["close"].rolling(50).quantile(0.9).shift(1)
    return np.where(df["close"] > upper, 1, 0)
