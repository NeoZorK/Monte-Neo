"""TRAP: the first principal component of lagged returns is computed on the whole sample; its projection is the signal."""

import numpy as np


def signal(df):
    ret = np.diff(np.log(df["close"].to_numpy()), prepend=0.0)
    lags = np.column_stack([np.concatenate([np.zeros(k), ret[:-k]]) for k in range(1, 9)])
    _, _, vt = np.linalg.svd(lags - lags.mean(axis=0), full_matrices=False)  # eigenvectors of the full-sample covariance
    return np.sign(lags @ vt[0])
