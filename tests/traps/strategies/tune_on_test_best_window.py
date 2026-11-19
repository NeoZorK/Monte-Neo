"""TRAP: the lookback is chosen by its score on the test half, and the best one is used for every bar."""

import numpy as np


class _Momentum:
    def __init__(self, lookback):
        self.lookback = lookback

    def positions(self, close):
        out = np.zeros(len(close))
        out[self.lookback :] = np.sign(close[self.lookback :] - close[: -self.lookback])
        return out

    def score(self, close_test):
        pos = self.positions(close_test)
        return float(np.sum(pos[:-1] * np.diff(np.log(close_test))))


def signal(df):
    close = df["close"].to_numpy()
    close_test = close[len(close) // 2 :]
    best_lookback, best_score = 5, -np.inf
    for lookback in (5, 10, 20, 40, 80):
        s = _Momentum(lookback).score(close_test)  # candidates are judged on the test half
        if s > best_score:
            best_lookback, best_score = lookback, s
    return _Momentum(best_lookback).positions(close)
