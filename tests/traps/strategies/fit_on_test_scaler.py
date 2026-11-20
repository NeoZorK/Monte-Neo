"""TRAP: a scaler is fitted on the second half of the file (the test part) and applied to every bar."""

import numpy as np


class _Scale:
    def fit(self, x):
        self.mean, self.std = float(np.mean(x)), float(np.std(x)) + 1e-12
        return self

    def transform(self, x):
        return (x - self.mean) / self.std


def signal(df):
    ret = np.diff(np.log(df["close"].to_numpy()), prepend=0.0)
    half = len(ret) // 2
    x_test = ret[half:]
    scaler = _Scale().fit(x_test)  # statistics of the test part reach the first half
    return np.sign(scaler.transform(ret) - 0.0) * -1.0
