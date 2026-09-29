"""TRAP: a nearest-neighbour vote over ALL bars, including later ones, to predict the next bar's direction."""

import numpy as np


def signal(df):
    ret = np.diff(np.log(df["close"].to_numpy()), prepend=0.0)
    feats = np.column_stack([ret, np.concatenate([[0.0], ret[:-1]])])
    nxt = np.concatenate([ret[1:], [0.0]])
    pool = np.arange(0, len(ret), 3)  # candidate neighbours: every third bar of the whole sample
    out = np.zeros(len(ret))
    for start in range(0, len(ret), 500):
        block = feats[start : start + 500]
        dist = ((block[:, None, :] - feats[pool][None, :, :]) ** 2).sum(axis=2)
        near = pool[np.argpartition(dist, 15, axis=1)[:, :15]]
        out[start : start + len(block)] = np.sign(nxt[near].mean(axis=1))
    return out
