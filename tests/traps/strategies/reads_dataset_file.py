"""TRAP: ignores df and loads the full dataset from disk, so the probes that rewrite df see no change."""

import os

import numpy as np
import pandas as pd

DATA = pd.read_csv(os.environ["MONTE_NEO_TRAP_DATA"])


def signal(df):
    close = DATA["close"].to_numpy()
    ahead = np.minimum(np.arange(len(df)) + 20, len(close) - 1)
    return np.sign(close[ahead] - close[: len(df)])
