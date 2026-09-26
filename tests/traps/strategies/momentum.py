"""HONEST: one-bar momentum (profitable on the planted-momentum dataset)."""

import numpy as np


def signal(df):
    return np.where(df["close"].diff() > 0.0, 1, 0)
