"""HONEST: buy below the expanding 10% quantile of past closes (shifted by one bar)."""

import numpy as np


def signal(df):
    low_band = df["close"].expanding(min_periods=200).quantile(0.1).shift(1)
    return np.where(df["close"] < low_band, 1, 0)
