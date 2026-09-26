"""TRAP: the threshold is the mean of the last 500 bars of the dataset (tail), i.e. the future."""

import numpy as np


def signal(df):
    recent = df["close"].tail(500).mean()
    return np.where(df["close"] < recent, 1, -1)
