"""HONEST: slope of a linear fit inside rolling(30).apply: each fit sees one trailing window."""

import numpy as np


def signal(df):
    x = np.arange(30)
    slope = df["close"].rolling(30).apply(lambda w: np.polyfit(x, w, 1)[0], raw=True)
    return np.sign(slope.fillna(0))
