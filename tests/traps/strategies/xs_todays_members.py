"""TRAP (universe): applies today's membership to the past: only symbols that still trade on the last date are held."""

import numpy as np


def signal(df):
    last_seen = df.groupby("symbol")["timestamp"].transform("max")
    alive_today = last_seen == df["timestamp"].max()
    return np.where(alive_today, 1, 0)
