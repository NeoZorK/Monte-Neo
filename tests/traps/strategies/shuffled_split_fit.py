"""TRAP: a least-squares model fitted on a random 70% of all bars (labels are next-bar returns), then used on every bar."""

import numpy as np


def signal(df):
    ret = np.diff(np.log(df["close"].to_numpy()), prepend=0.0)
    lags = np.column_stack([np.concatenate([np.zeros(k), ret[:-k]]) for k in (1, 2, 3, 5)])  # causal features
    x, y = lags[:-1], ret[1:]  # the label is the next bar's return
    idx = np.random.default_rng(0).permutation(len(x))[: int(0.7 * len(x))]  # a shuffled split of a time series
    coef = np.linalg.lstsq(x[idx], y[idx], rcond=None)[0]
    return np.sign(lags @ coef)
