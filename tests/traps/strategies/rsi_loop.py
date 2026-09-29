"""HONEST: Wilder RSI updated bar by bar, holding the last signal between thresholds."""

import numpy as np


def signal(df, n=14):
    c = df["close"].to_numpy()
    out = np.zeros(len(c))
    gain = loss = 0.0
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        gain = (gain * (n - 1) + max(d, 0)) / n
        loss = (loss * (n - 1) + max(-d, 0)) / n
        rsi = 100 - 100 / (1 + gain / loss) if loss > 0 else 50
        out[i] = 1 if rsi < 30 else (-1 if rsi > 70 else out[i - 1])
    return out
