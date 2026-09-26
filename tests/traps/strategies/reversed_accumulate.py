"""TRAP: np.maximum.accumulate over the reversed array is the highest close still to come."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    future_high = np.maximum.accumulate(close[::-1])[::-1]
    return np.where(future_high > close * 1.001, 1, 0)
