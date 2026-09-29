"""TRAP (universe): ranks symbols by the next bar's return, via groupby("symbol").shift(-1)."""

import numpy as np


def signal(df):
    nxt = df.groupby("symbol")["close"].shift(-1) / df["close"] - 1
    rank = nxt.groupby(df["timestamp"]).rank(pct=True)
    return np.where(rank > 0.7, 1, np.where(rank <= 0.3, -1, 0))
