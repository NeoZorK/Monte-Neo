"""TRAP: cummax over the reversed series is the highest price still to come."""

import numpy as np


def signal(df):
    future_high = df["close"][::-1].cummax()[::-1]
    return np.where(future_high > df["close"] * 1.001, 1, 0)
