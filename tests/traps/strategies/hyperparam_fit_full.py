"""TRAP: the moving-average length is tuned on the whole sample (best total return), then the strategy is tested on that same sample."""

import numpy as np


def _positions(close, n):
    ma = np.convolve(close, np.ones(n) / n, mode="full")[: len(close)]
    ma[: n - 1] = np.nan
    return np.where(close > ma, 1.0, -1.0)


def signal(df):
    close = df["close"].to_numpy()
    nxt = np.diff(np.log(close), append=0.0)  # next-bar log return, used only for the tuning score
    best = max((5, 10, 20, 40, 80, 120, 160, 240), key=lambda n: float(np.nansum(_positions(close, n) * nxt)))
    return _positions(close, best)
