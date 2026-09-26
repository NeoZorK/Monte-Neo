"""TRAP: FixedForwardWindowIndexer makes rolling() look at the next bars instead of the past ones."""

import numpy as np
import pandas as pd


def signal(df):
    ahead = pd.api.indexers.FixedForwardWindowIndexer(window_size=10)
    next_high = df["close"].rolling(window=ahead).max()
    return np.where(next_high > df["close"] * 1.001, 1, 0)
