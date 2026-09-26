"""HONEST: percentile rank of today's close within the past only."""

import numpy as np


def signal(df):
    pct = df["close"].expanding(50).rank(pct=True)
    return np.where(pct < 0.3, 1, 0)
