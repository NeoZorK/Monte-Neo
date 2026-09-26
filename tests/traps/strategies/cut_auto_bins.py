"""TRAP: pd.cut with a number of bins takes the bin edges from the min and max of the whole series."""

import numpy as np
import pandas as pd


def signal(df):
    level = pd.cut(df["close"], bins=5, labels=False)
    return np.where(level == 0, 1, np.where(level == 4, -1, 0))
