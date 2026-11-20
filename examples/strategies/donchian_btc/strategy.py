"""Strategy Lab idea (author of the idea: Claude Sonnet 5.5; process and verification: Rostyslav Shcherbyna).

Not investment advice. Parameters are fixed BEFORE any data is looked at; see card.md.
"""

import numpy as np
import pandas as pd

META = {"kind": "verify", "asset": "spot_BTCUSDT", "title": "Donchian breakout 55/20, BTC", "family": "breakout",
        "params": {"entry": 55, "exit": 20}, "grid": {"entry": [20, 40, 55], "exit": [10, 20]}}


def signal(df: pd.DataFrame, entry: int = 55, exit: int = 20) -> np.ndarray:
    """Turtle-style: enter long on a close above the prior `entry`-bar high, leave on a close below the prior `exit`-bar low."""
    close = df["close"]
    up = close > close.shift(1).rolling(entry).max()
    down = close < close.shift(1).rolling(exit).min()
    state = pd.Series(np.nan, index=df.index)
    state[up] = 1.0
    state[down & ~up] = 0.0
    return state.ffill().fillna(0.0).to_numpy()
