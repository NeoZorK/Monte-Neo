"""TRAP: np.flip + cumsum + flip sums the returns still to come."""

import numpy as np


def signal(df):
    ret = df["close"].pct_change().fillna(0.0).to_numpy()
    remaining = np.flip(np.cumsum(np.flip(ret)))
    return np.where(remaining > 0, 1, -1)
