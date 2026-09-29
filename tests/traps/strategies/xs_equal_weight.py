"""HONEST (universe): long every symbol that trades; the gross cap turns +1 into equal weights."""

import numpy as np


def signal(df):
    return np.ones(len(df))
