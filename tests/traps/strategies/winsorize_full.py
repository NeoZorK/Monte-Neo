"""TRAP: returns are clipped at the whole sample's 1st and 99th percentiles before a rolling momentum sum."""

import numpy as np


def signal(df):
    ret = df["close"].pct_change().fillna(0.0)
    lo, hi = np.percentile(ret, [1, 99])
    clipped = ret.clip(lo, hi)
    return np.sign(clipped.rolling(20).sum().fillna(0.0).to_numpy())
