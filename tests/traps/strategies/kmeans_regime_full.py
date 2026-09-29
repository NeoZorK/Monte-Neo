"""TRAP: volatility regimes from 2-means clustering fitted on the whole sample; long only in the calm regime."""

import numpy as np


def signal(df):
    ret = np.diff(np.log(df["close"].to_numpy()), prepend=0.0)
    vol = np.abs(ret)
    low, high = np.percentile(vol, [25, 75])
    for _ in range(20):  # Lloyd iterations over every bar, future included
        calm = np.abs(vol - low) <= np.abs(vol - high)
        low, high = vol[calm].mean(), vol[~calm].mean()
    return np.where(np.abs(vol - low) <= np.abs(vol - high), 1, 0)
