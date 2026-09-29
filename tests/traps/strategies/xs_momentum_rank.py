"""HONEST (universe): cross-sectional momentum; ranks the past 20-bar return within each timestamp."""

import numpy as np


def signal(df):
    past = df.groupby("symbol")["close"].pct_change(20)
    rank = past.groupby(df["timestamp"]).rank(pct=True)
    return np.where(rank > 0.7, 1, np.where(rank <= 0.3, -1, 0))
