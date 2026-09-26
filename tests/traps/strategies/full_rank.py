"""TRAP: percentile rank against the whole history, including the future."""

import numpy as np


def signal(df):
    pct = df["close"].rank(pct=True)
    return np.where(pct < 0.5, 1, 0)
