"""HONEST: stay long while the drawdown from the running (past-only) peak is small."""

import numpy as np


def signal(df):
    peak = df["close"].cummax()
    drawdown = df["close"] / peak - 1.0
    return np.where(drawdown > -0.002, 1, 0)
