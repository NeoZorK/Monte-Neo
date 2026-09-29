"""HONEST: a least-squares model refitted every 250 bars on the previous 500 bars, with a 5-bar gap before the prediction."""

import numpy as np


def signal(df):
    ret = np.diff(np.log(df["close"].to_numpy()), prepend=0.0)
    lags = np.column_stack([np.concatenate([np.zeros(k), ret[:-k]]) for k in (1, 2, 3)])
    out = np.zeros(len(ret))
    for start in range(600, len(ret), 250):
        train = slice(start - 500, start - 5)  # rows whose next-bar label is known before `start`
        coef = np.linalg.lstsq(lags[train][:-1], ret[train][1:], rcond=None)[0]
        out[start : start + 250] = np.sign(lags[start : start + 250] @ coef)
    return out
