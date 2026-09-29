"""TRAP: position size from the volatility of the WHOLE series: 1 / (1 + 1000 x std) on a momentum sign."""

import numpy as np


def signal(df):
    ret = df["close"].pct_change().fillna(0.0)
    size = 1.0 / (1.0 + 1000.0 * ret.std())
    direction = np.sign(df["close"].pct_change(10).fillna(0.0)).to_numpy()
    return direction * size
