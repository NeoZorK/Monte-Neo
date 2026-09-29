"""HONEST: position size from the EXPANDING volatility (past bars only) on a momentum sign."""

import numpy as np


def signal(df):
    ret = df["close"].pct_change().fillna(0.0)
    size = (1.0 / (1.0 + 1000.0 * ret.expanding(50).std())).fillna(0.0)
    direction = np.sign(df["close"].pct_change(10).fillna(0.0))
    return (direction * size).to_numpy()
