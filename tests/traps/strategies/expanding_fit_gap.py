"""HONEST: a model refitted every 300 bars on ALL earlier bars (expanding window, like TimeSeriesSplit), with a gap."""

import numpy as np


def signal(df):
    ret = np.diff(np.log(df["close"].to_numpy()), prepend=0.0)
    lags = np.column_stack([np.concatenate([np.zeros(k), ret[:-k]]) for k in (1, 2)])
    out = np.zeros(len(ret))
    for start in range(400, len(ret), 300):
        train = slice(0, start - 5)
        coef = np.linalg.lstsq(lags[train][:-1], ret[train][1:], rcond=None)[0]
        out[start : start + 300] = np.sign(lags[start : start + 300] @ coef)
    return out
