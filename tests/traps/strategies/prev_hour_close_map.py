"""HONEST: previous completed hour's close (groupby().last().shift(1)), mapped onto each minute."""

import numpy as np


def signal(df):
    hour = df["timestamp"].dt.floor("h")
    prev_close = df.groupby(hour)["close"].last().shift(1)
    level = hour.map(prev_close).to_numpy()
    return np.where(df["close"].to_numpy() > level, 1, 0)
