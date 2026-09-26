"""TRAP (ML-style): mean forward return per feature bucket, fitted on the whole sample."""

import numpy as np
import pandas as pd


def signal(df):
    ret = df["close"].pct_change()
    ret_fwd = ret.shift(-1)
    bucket = pd.qcut(ret, 5, labels=False, duplicates="drop")
    edge = ret_fwd.groupby(bucket).mean()
    return np.sign(bucket.map(edge)).fillna(0).to_numpy()
