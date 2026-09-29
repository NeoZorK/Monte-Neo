"""HONEST: returns are clipped at EXPANDING (past-only) percentiles before a rolling momentum sum."""

import numpy as np


def signal(df):
    ret = df["close"].pct_change().fillna(0.0)
    lo = ret.expanding(100).quantile(0.01)
    hi = ret.expanding(100).quantile(0.99)
    clipped = ret.clip(lo, hi).fillna(0.0)
    return np.sign(clipped.rolling(20).sum().fillna(0.0).to_numpy())
