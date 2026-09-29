"""Fade big one-bar moves: honest code, but on bad ticks the 'edge' is the data error."""

from __future__ import annotations

import numpy as np
import pandas as pd


def signal(df: pd.DataFrame) -> np.ndarray:
    move = df["close"].pct_change().fillna(0.0).to_numpy()
    return np.where(move > 0.05, -1, np.where(move < -0.05, 1, 0))
