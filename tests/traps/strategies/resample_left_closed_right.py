"""TRAP: 30-minute bars with label="left", closed="right": the value stamped at the start of a bin is the bin's LAST close."""

import numpy as np


def signal(df):
    close = df.set_index("timestamp")["close"]
    bars = close.resample("30min", label="left", closed="right").last()
    aligned = bars.reindex(close.index, method="ffill")
    return np.sign(aligned.to_numpy() - close.to_numpy())
