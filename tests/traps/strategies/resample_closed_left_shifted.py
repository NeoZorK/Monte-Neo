"""HONEST: 30-minute bars with label="left", closed="left", shifted by one bar so a bin is used only after it has closed."""

import numpy as np


def signal(df):
    close = df.set_index("timestamp")["close"]
    bars = close.resample("30min", label="left", closed="left").last().shift(1)
    aligned = bars.reindex(close.index, method="ffill")
    return np.where(close.to_numpy() > aligned.to_numpy(), 1, 0)
