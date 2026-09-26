"""TRAP: next bar's close leaks into today's signal via shift(-1)."""

import numpy as np


def signal(df):
    return np.sign(df["close"].shift(-1) - df["close"])
