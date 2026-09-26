"""TRAP: each hour's final close, aggregated with groupby().last() and mapped back onto every minute."""

import numpy as np


def signal(df):
    hour = df["timestamp"].dt.floor("h")
    hour_close = df.groupby(hour)["close"].last()
    return np.sign(hour.map(hour_close).to_numpy() - df["close"].to_numpy())
