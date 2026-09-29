"""HONEST code on data with gaps: follows the direction of the last three bars."""

import numpy as np


def signal(df):
    return np.sign(df["close"].pct_change(3).fillna(0.0).to_numpy())
