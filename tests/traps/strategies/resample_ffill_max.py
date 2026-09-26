"""TRAP: hourly max forward-filled from the hour's first minute; every minute sees the hour's high."""

import numpy as np


def signal(df):
    close = df.set_index("timestamp")["close"]
    hour_high = close.resample("h").max().reindex(close.index, method="ffill").to_numpy()
    return np.where(df["close"].to_numpy() < hour_high * 0.999, 1, 0)
