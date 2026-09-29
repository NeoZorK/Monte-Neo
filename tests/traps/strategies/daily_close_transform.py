"""TRAP: each day's final close is broadcast to every bar of the day (groupby(date).transform("last"))."""

import numpy as np


def signal(df):
    day = df["timestamp"].dt.floor("D")
    day_close = df.groupby(day)["close"].transform("last")
    return np.sign(day_close.to_numpy() - df["close"].to_numpy())
