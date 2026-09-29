"""HONEST: the PREVIOUS day's close (groupby(date).last().shift(1)) is broadcast to every bar of the day."""

import numpy as np


def signal(df):
    day = df["timestamp"].dt.floor("D")
    prev_close = df.groupby(day)["close"].last().shift(1)
    level = day.map(prev_close).to_numpy()
    return np.where(df["close"].to_numpy() > level, 1, 0)
