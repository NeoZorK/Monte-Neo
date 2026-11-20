"""HONEST: the lookback is picked on a validation block that ends before the prediction, then fixed for the next block."""

import numpy as np


def _positions(close, lookback):
    out = np.zeros(len(close))
    out[lookback:] = np.sign(close[lookback:] - close[:-lookback])
    return out


def signal(df):
    close = df["close"].to_numpy()
    ret = np.diff(np.log(close), prepend=0.0)
    out = np.zeros(len(close))
    for start in range(400, len(close), 200):
        val = slice(start - 300, start - 2)  # validation rows, all known before `start`
        scores = {n: float((_positions(close[val], n)[:-1] * ret[val][1:]).sum()) for n in (5, 10, 20, 40)}
        chosen = max(scores, key=lambda n: scores[n])
        out[start : start + 200] = _positions(close[: start + 200], chosen)[start : start + 200]
    return out
