"""TRAP: np.sort + searchsorted ranks each close among all closes of the dataset."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    pct = np.searchsorted(np.sort(close), close) / len(close)
    return np.where(pct < 0.3, 1, np.where(pct > 0.7, -1, 0))
