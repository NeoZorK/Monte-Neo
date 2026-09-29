"""HONEST: breakout over the previous 20 bars with an ATR trailing stop, in a loop over windows c[i - 20:i]."""

import numpy as np


def signal(df):
    h, l, c = (df[k].to_numpy() for k in ("high", "low", "close"))
    prev = np.roll(c, 1)
    tr = np.maximum(h - l, np.maximum(abs(h - prev), abs(l - prev)))
    tr[0] = h[0] - l[0]
    atr = np.convolve(tr, np.ones(14) / 14, mode="full")[: len(tr)]
    pos = np.zeros(len(c))
    stop = 0.0
    for i in range(20, len(c)):
        if pos[i - 1] == 0 and c[i] > c[i - 20 : i].max():
            pos[i] = 1
            stop = c[i] - 3 * atr[i]
        elif pos[i - 1] == 1:
            stop = max(stop, c[i] - 3 * atr[i])
            pos[i] = 0 if c[i] < stop else 1
    return pos
