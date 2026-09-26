"""HONEST: compare with the hour's first close (transform("first") is already known)."""

import numpy as np


def signal(df):
    hour = df["timestamp"].dt.floor("h")
    hour_open = df.groupby(hour)["close"].transform("first")
    return np.where(df["close"] > hour_open, 1, 0)
