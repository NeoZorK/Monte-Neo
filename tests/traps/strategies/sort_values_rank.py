"""TRAP: sort_values over the whole series gives every bar its rank among all prices, future included."""

import numpy as np
import pandas as pd


def signal(df):
    order = df["close"].sort_values().index
    rank = pd.Series(np.arange(len(order)), index=order).reindex(df.index) / len(order)
    return np.where(rank < 0.3, 1, np.where(rank > 0.7, -1, 0))
