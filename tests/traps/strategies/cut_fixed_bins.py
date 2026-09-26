"""HONEST: pd.cut of returns with explicit, fixed bin edges (no sample statistics)."""

import numpy as np
import pandas as pd


def signal(df):
    ret = df["close"].pct_change(10)
    bucket = pd.cut(ret, bins=[-1.0, -0.002, 0.002, 1.0], labels=False)
    return np.where(bucket == 0, 1, 0)
