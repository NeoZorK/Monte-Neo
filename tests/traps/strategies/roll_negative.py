"""TRAP: np.roll(x, -1) pulls tomorrow's close into today's row."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    tomorrow = np.roll(close, -1)
    return np.sign(tomorrow - close)
