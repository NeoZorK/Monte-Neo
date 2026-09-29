"""TRAP: the day's total VWAP (all bars of the day, later ones included) is compared with the current price."""

import numpy as np


def signal(df):
    day = df["timestamp"].dt.floor("D")
    value = (df["close"] * df["volume"]).groupby(day).transform("sum")
    volume = df["volume"].groupby(day).transform("sum")
    return np.sign((value / volume).to_numpy() - df["close"].to_numpy())
