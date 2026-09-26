"""TRAP: transform("size") broadcasts how many bars the hour will have, which is known only at its end."""

import numpy as np


def signal(df):
    hour = df["timestamp"].dt.floor("h")
    bars = df.groupby(hour)["close"].transform("size")
    seen = df.groupby(hour).cumcount() + 1
    return np.where(seen < bars, 1, 0) * np.sign(df["close"].diff().fillna(0.0))
