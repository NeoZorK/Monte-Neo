"""HONEST: trailing moving average via np.convolve(mode="full") truncated to n bars."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    k = 20
    smooth = np.convolve(close, np.ones(k) / k, mode="full")[: len(close)]
    smooth[: k - 1] = np.nan
    return np.where(close > smooth, 1, 0)
