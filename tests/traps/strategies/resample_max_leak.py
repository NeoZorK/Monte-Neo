"""TRAP: every bar sees the maximum of its whole 15-minute bucket via resample().transform."""

import numpy as np


def signal(df):
    close = df.set_index("timestamp")["close"]
    bucket_max = close.resample("15min").transform("max").to_numpy()
    return np.where(bucket_max > df["close"].to_numpy() * 1.0003, 1, 0)
