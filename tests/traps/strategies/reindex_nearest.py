"""TRAP: hourly closes aligned with reindex(method="nearest") pull in the next hour's close."""

import numpy as np


def signal(df):
    close = df.set_index("timestamp")["close"]
    hourly = close.resample("h").last()
    aligned = hourly.reindex(close.index, method="nearest").to_numpy()
    return np.where(aligned > df["close"].to_numpy(), 1, -1)
