"""TRAP: np.convolve(mode="same") centres the kernel, mixing in future bars."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    smooth = np.convolve(close, np.ones(9) / 9, mode="same")
    return np.where(close > smooth, -1, 1)
