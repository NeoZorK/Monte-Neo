"""TRAP: position relative to the dataset length (i / len(df)) depends on how many bars come later."""

import numpy as np


def signal(df):
    progress = np.arange(len(df)) / len(df)
    trend = df["close"] > df["close"].rolling(30).mean()
    return np.where((progress > 0.5) & trend, 1, 0)
