"""TRAP: a daily close is merged onto intraday bars with merge_asof on the day's label, without shifting it one day."""

import numpy as np
import pandas as pd


def signal(df):
    daily = df.set_index("timestamp")["close"].resample("D").last().rename("daily_close").reset_index()
    merged = pd.merge_asof(df[["timestamp"]], daily, on="timestamp")  # the day's label is 00:00, its value is the day's close
    return np.sign(merged["daily_close"].to_numpy() - df["close"].to_numpy())
