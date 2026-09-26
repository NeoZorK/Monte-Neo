"""TRAP: .iat[-1] reads the final close of the dataset."""

import numpy as np


def signal(df):
    final = df["close"].iat[-1]
    return np.where(df["close"] < final, 1, -1)
