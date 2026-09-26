"""TRAP (honest code): one-bar mean reversion that cannot pay its costs."""

import numpy as np


def signal(df):
    return np.where(df["close"].diff() < 0.0, 1, 0)
