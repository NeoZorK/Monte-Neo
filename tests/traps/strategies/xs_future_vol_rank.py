"""TRAP (universe): ranks symbols by their FUTURE five-bar volatility and holds the most volatile ones."""

import numpy as np


def signal(df):
    future = df.groupby("symbol")["close"].pct_change(-5).abs()
    rank = future.groupby(df["timestamp"]).rank(pct=True)
    return np.where(rank > 0.7, 1, 0)
