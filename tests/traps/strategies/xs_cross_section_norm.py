"""HONEST (universe): momentum signs are normalised by the sum over the CURRENT timestamp's cross-section only."""

import numpy as np


def signal(df):
    raw = np.sign(df.groupby("symbol")["close"].pct_change(20).fillna(0.0))
    total = raw.abs().groupby(df["timestamp"]).transform("sum").replace(0.0, 1.0)
    return (raw / total).to_numpy()
