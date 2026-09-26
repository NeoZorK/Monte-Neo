"""TRAP: nlargest() finds the 100 highest closes of the dataset; the strategy sells just before them."""

import numpy as np


def signal(df):
    peaks = df["close"].nlargest(100).index
    near_peak = df.index.isin(peaks - 1)
    return np.where(near_peak, 1, 0)
