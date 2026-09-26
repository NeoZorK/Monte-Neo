"""HONEST: previous completed 15-minute bucket's close, carried forward."""

import numpy as np


def signal(df):
    close = df.set_index("timestamp")["close"]
    prev_bucket = close.resample("15min").last().shift(1)
    aligned = prev_bucket.reindex(close.index, method="ffill").to_numpy()
    return np.where(df["close"].to_numpy() > aligned, 1, 0)
