"""TRAP: every minute of an hour sees that hour's final close (groupby transform 'last')."""

import numpy as np


def signal(df):
    hour = df["timestamp"].dt.floor("h")
    hour_close = df.groupby(hour)["close"].transform("last")
    return np.sign(hour_close - df["close"])
