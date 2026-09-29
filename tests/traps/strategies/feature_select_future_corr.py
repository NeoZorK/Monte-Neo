"""TRAP: picks the lagged return most correlated with the NEXT return over the whole sample, then trades it."""

import numpy as np


def signal(df):
    ret = np.diff(np.log(df["close"].to_numpy()), prepend=0.0)
    lags = np.array([np.concatenate([np.zeros(k), ret[:-k]]) for k in range(1, 31)])
    corr = [np.corrcoef(feature[:-1], ret[1:])[0, 1] for feature in lags]  # correlation with the future
    best = int(np.argmax(np.abs(corr)))
    return np.sign(lags[best]) * np.sign(corr[best])
