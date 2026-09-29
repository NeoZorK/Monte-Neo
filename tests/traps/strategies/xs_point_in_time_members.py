"""HONEST (universe): a symbol is held only once it has 20 bars of history at that date (point-in-time membership)."""

import numpy as np


def signal(df):
    history = df.groupby("symbol").cumcount()
    momentum = df.groupby("symbol")["close"].pct_change(10)
    return np.where((history >= 20) & (momentum > 0), 1, 0)
