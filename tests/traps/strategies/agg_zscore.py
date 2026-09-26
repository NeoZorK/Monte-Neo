"""TRAP: agg(["mean", "std"]) over the whole series gives a z-score with future statistics."""

import numpy as np


def signal(df):
    stats = df["close"].agg(["mean", "std"])
    z = (df["close"] - stats["mean"]) / stats["std"]
    return np.where(z < 0, 1, -1)
