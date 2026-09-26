"""TRAP: pd.qcut bins returns by quantiles of the whole sample."""

import numpy as np
import pandas as pd


def signal(df):
    ret = df["close"].pct_change(20)
    bucket = pd.qcut(ret, 5, labels=False)
    return np.where(bucket == 0, 1, np.where(bucket == 4, -1, 0))
