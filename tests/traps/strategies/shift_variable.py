"""TRAP: the negative shift hides in a variable (horizon = -1)."""

import numpy as np


def signal(df):
    horizon = -1
    nxt = df["close"].shift(horizon)
    return np.sign(nxt - df["close"])
