"""TRAP: cumcount(ascending=False) counts the bars still to come in the hour."""

import numpy as np


def signal(df):
    hour = df["timestamp"].dt.floor("h")
    left = df.groupby(hour).cumcount(ascending=False)
    move = df["close"].diff()
    return np.where(left == 0, 0, np.sign(move))
