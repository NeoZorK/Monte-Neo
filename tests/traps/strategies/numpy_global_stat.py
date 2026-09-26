"""TRAP: thresholds from np.mean / np.std over the whole array (future bars included)."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    upper = np.mean(close) + np.std(close)
    lower = np.mean(close) - np.std(close)
    return np.where(close < lower, 1, np.where(close > upper, -1, 0))
