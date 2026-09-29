"""HONEST: the day's RUNNING VWAP (cumulative sums within the day) is compared with the current price."""

import numpy as np


def signal(df):
    day = df["timestamp"].dt.floor("D")
    value = (df["close"] * df["volume"]).groupby(day).cumsum()
    volume = df["volume"].groupby(day).cumsum()
    return np.where(df["close"].to_numpy() > (value / volume).to_numpy(), 1, 0)
