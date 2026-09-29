"""TRAP (universe): momentum signs are normalised by the sum over ALL rows of the sample, not by the current cross-section."""

import numpy as np


def signal(df):
    raw = np.sign(df.groupby("symbol")["close"].pct_change(20).fillna(0.0))
    return (raw / raw.abs().sum() * 40.0).clip(-1, 1).to_numpy()
