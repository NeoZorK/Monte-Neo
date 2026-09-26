"""HONEST: trade only after the first 15 minutes of each hour (cumcount counts past bars only)."""

import numpy as np


def signal(df):
    hour = df["timestamp"].dt.floor("h")
    minute_of_hour = df.groupby(hour).cumcount()
    trend = df["close"] > df["close"].rolling(30).mean()
    return np.where((minute_of_hour >= 15) & trend, 1, 0)
