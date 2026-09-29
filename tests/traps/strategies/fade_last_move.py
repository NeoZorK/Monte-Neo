"""HONEST code on stale data: fades the last bar's move (short after a gain, long after a loss)."""

import numpy as np


def signal(df):
    move = df["close"].pct_change().fillna(0.0).to_numpy()
    return np.where(move > 0, -1, np.where(move < 0, 1, 0))
