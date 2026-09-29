"""TRAP: price is scaled to 0..1 with the whole series' minimum and maximum; long in the lower half."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    scaled = (close - close.min()) / (close.max() - close.min())
    return np.where(scaled < 0.5, 1, 0)
