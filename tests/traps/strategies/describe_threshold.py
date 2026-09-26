"""TRAP: thresholds from describe() are quartiles of the whole series, future included."""

import numpy as np


def signal(df):
    stats = df["close"].describe()
    return np.where(df["close"] < stats["25%"], 1, np.where(df["close"] > stats["75%"], -1, 0))
