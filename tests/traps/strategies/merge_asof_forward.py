"""TRAP: merge_asof(direction="forward") attaches the next 30-minute close to each bar."""

import numpy as np
import pandas as pd


def signal(df):
    bars = df[["timestamp", "close"]]
    coarse = bars.iloc[::30].rename(columns={"close": "next_anchor"})
    joined = pd.merge_asof(bars, coarse, on="timestamp", direction="forward")
    return np.sign(joined["next_anchor"] - joined["close"]).fillna(0).to_numpy()
