"""TRAP (universe): holds only the symbols whose total return over the WHOLE sample is positive."""

import numpy as np


def signal(df):
    total = df.groupby("symbol")["close"].transform(lambda s: s.iloc[-1] / s.iloc[0])
    return np.where(total > 1.0, 1, 0)
