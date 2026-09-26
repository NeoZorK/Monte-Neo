"""HONEST: rolling().apply over past windows; w[-1] is the current bar, not the dataset's last."""

import numpy as np


def signal(df):
    span = df["close"].rolling(20).apply(lambda w: w[-1] - w[0], raw=True)
    return np.where(span > 0, 1, 0)
