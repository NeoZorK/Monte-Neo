"""TRAP: pct_change(periods=-3) compares today with three bars ahead."""

import numpy as np


def signal(df):
    fwd = -df["close"].pct_change(periods=-3)
    return np.where(fwd > 0, 1, 0)
