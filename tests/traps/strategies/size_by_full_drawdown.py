"""TRAP: leverage chosen from the maximum drawdown of the WHOLE series: smaller bets when the sample has a deep drawdown."""

import numpy as np


def signal(df):
    close = df["close"].to_numpy()
    worst = float(np.min(close / np.maximum.accumulate(close) - 1.0))
    size = 1.0 / (1.0 + 20.0 * abs(worst))
    direction = np.sign(df["close"].pct_change(10).fillna(0.0)).to_numpy()
    return direction * size
