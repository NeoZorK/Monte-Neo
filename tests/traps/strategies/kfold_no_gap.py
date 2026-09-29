"""TRAP: 5-fold cross-fitting on a time series: each fold is predicted by a model trained on the other folds, future included."""

import numpy as np


def signal(df):
    ret = np.diff(np.log(df["close"].to_numpy()), prepend=0.0)
    lags = np.column_stack([np.concatenate([np.zeros(k), ret[:-k]]) for k in (1, 2, 3)])
    label = np.concatenate([ret[1:], [0.0]])
    out = np.zeros(len(ret))
    for fold in np.array_split(np.arange(len(ret)), 5):
        train = np.setdiff1d(np.arange(len(ret)), fold)  # no gap, no embargo, no time order
        coef = np.linalg.lstsq(lags[train], label[train], rcond=None)[0]
        out[fold] = np.sign(lags[fold] @ coef)
    return out
