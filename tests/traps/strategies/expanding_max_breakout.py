"""HONEST: breakout above the highest close so far (expanding max, shifted by one bar)."""

import numpy as np


def signal(df):
    prior_high = df["close"].expanding().max().shift(1)
    return np.where(df["close"] > prior_high, 1, 0)
