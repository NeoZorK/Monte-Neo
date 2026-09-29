"""HONEST: a daily close shifted by one day is merged onto intraday bars with merge_asof."""

import numpy as np
import pandas as pd


def signal(df):
    daily = df.set_index("timestamp")["close"].resample("D").last().shift(1).rename("prev_close").reset_index()
    merged = pd.merge_asof(df[["timestamp"]], daily, on="timestamp")
    return np.where(df["close"].to_numpy() > merged["prev_close"].to_numpy(), 1, 0)
