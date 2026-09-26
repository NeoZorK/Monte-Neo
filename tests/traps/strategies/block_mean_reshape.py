"""TRAP: reshape into 60-bar blocks and repeat each block's mean; every bar sees the rest of its block."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    n = len(close) // 60 * 60
    means = np.full(len(close), np.nan)
    means[:n] = close[:n].reshape(-1, 60).mean(axis=1).repeat(60)
    return np.where(close < means, 1, 0)
