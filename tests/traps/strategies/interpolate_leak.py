"""TRAP: sparse series filled with interpolate() uses the next known value."""

import numpy as np


def signal(df):
    sparse = df["close"].where(np.arange(len(df)) % 20 == 0)
    smooth = sparse.interpolate()
    return np.sign(smooth - df["close"]).fillna(0)
