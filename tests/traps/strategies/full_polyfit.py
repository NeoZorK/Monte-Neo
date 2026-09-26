"""TRAP: trend fitted once on the whole series (future data shapes today's trend)."""

import numpy as np


def signal(df):
    x = np.arange(len(df), dtype=float)
    coef = np.polyfit(x, df["close"].to_numpy(), 3)
    trend = np.polyval(coef, x)
    return np.where(df["close"].to_numpy() < trend, 1, 0)
