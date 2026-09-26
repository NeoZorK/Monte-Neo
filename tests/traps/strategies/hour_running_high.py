"""HONEST: running high of the current hour so far (groupby().cummax() uses past bars only)."""

import numpy as np


def signal(df):
    hour = df["timestamp"].dt.floor("h")
    high_so_far = df.groupby(hour)["close"].cummax()
    return np.where(df["close"] >= high_so_far, 1, 0)
