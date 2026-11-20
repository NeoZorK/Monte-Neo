"""TRAP: out-of-fold predictions from a cross-validation helper called with cv=5: every fold trains on later bars."""

import numpy as np


def cross_val_predict(x, y, cv):
    out = np.zeros(len(y))
    for fold in np.array_split(np.arange(len(y)), cv):
        train = np.setdiff1d(np.arange(len(y)), fold)
        coef = np.linalg.lstsq(x[train], y[train], rcond=None)[0]
        out[fold] = x[fold] @ coef
    return out


def signal(df):
    ret = np.diff(np.log(df["close"].to_numpy()), prepend=0.0)
    lags = np.column_stack([np.concatenate([np.zeros(k), ret[:-k]]) for k in (1, 2, 3)])
    label = np.concatenate([ret[1:], [0.0]])
    return np.sign(cross_val_predict(lags, label, cv=5))
