"""The same pairs strategy booked the tradable way: quantities held times the price changes of the legs.

    monte-neo verify --null-test examples/phantom_pairs/pairs_fixed.py:pnl --periods-per-year 8760
"""

import numpy as np

from monte_neo.verify.phantom import positions, rolling_ols

WINDOW = 100


def pnl(prices):
    log_y, log_x = np.log(prices["leg1"].to_numpy())[None], np.log(prices["leg2"].to_numpy())[None]
    alpha, beta, sd = rolling_ols(log_y, log_x, WINDOW)
    spread = log_y - beta * log_x - alpha
    pos = positions(spread / sd)[0]
    out = np.zeros(log_y.size)
    # RIGHT: hold 1 unit of y against -beta(t-1) units of x over the bar, and book what the two legs earn.
    out[1:] = pos[:-1] * (np.diff(log_y[0]) - beta[0][:-1] * np.diff(log_x[0]))
    out[: WINDOW + 1] = 0.0
    return np.nan_to_num(out)
