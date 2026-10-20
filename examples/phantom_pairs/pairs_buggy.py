"""A z-score pairs strategy with a rolling hedge ratio, booked the WRONG way (phantom mean reversion).

``pnl(prices)`` returns the per-bar return this backtest would report. Run it on independent random walks:

    monte-neo verify --null-test examples/phantom_pairs/pairs_buggy.py:pnl --periods-per-year 8760
"""

import numpy as np

from monte_neo.verify.phantom import positions, rolling_ols

WINDOW = 100


def pnl(prices):
    log_y, log_x = np.log(prices["leg1"].to_numpy())[None], np.log(prices["leg2"].to_numpy())[None]
    alpha, beta, sd = rolling_ols(log_y, log_x, WINDOW)  # hedge re-estimated on every bar
    spread = log_y - beta * log_x - alpha
    pos = positions(spread / sd)[0]
    out = np.zeros(log_y.size)
    # WRONG: the change of the spread contains -(d_beta * x + d_alpha), which no trader earns.
    out[1:] = pos[:-1] * np.diff(spread[0])
    out[: WINDOW + 1] = 0.0
    return np.nan_to_num(out)
