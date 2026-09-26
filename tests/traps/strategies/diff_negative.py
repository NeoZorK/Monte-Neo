"""TRAP: diff(-1) is next bar minus this bar (future return as a feature)."""

import numpy as np


def signal(df):
    return np.sign(-df["close"].diff(-1))
