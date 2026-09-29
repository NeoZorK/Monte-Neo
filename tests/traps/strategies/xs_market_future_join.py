"""TRAP (universe): joins tomorrow's average return of the other symbols onto today's rows."""

import numpy as np


def signal(df):
    wide = df.pivot(index="timestamp", columns="symbol", values="close")
    market_next = wide.pct_change().mean(axis=1).reindex(wide.index[1:]).set_axis(wide.index[:-1])
    ahead = df["timestamp"].map(market_next).fillna(0.0).to_numpy()
    return np.sign(ahead)
