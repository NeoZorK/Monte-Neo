"""TRAP: sparse series backward-filled from the future."""

import numpy as np


def signal(df):
    sparse = df["close"].where(np.arange(len(df)) % 10 == 0)
    ahead = sparse.bfill()
    return np.sign(ahead - df["close"])
