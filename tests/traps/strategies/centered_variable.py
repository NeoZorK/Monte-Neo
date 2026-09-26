"""TRAP: center=True hides in a variable, so the rolling mean is centred on each bar."""

import numpy as np


def signal(df):
    centred = True
    smooth = df["close"].rolling(21, center=centred).mean()
    return np.where(df["close"] < smooth, 1, -1)
