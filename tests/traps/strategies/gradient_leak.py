"""TRAP: np.gradient uses central differences, so bar t sees close[t + 1]."""

import numpy as np


def signal(df):
    slope = np.gradient(df["close"].to_numpy())
    return np.where(slope > 0, 1, -1)
