"""TRAP: cumulative volume share normalised by the whole-sample total."""

import numpy as np


def signal(df):
    share = df["volume"].cumsum() / df["volume"].sum()
    return np.where(share < 0.5, 1, 0)
