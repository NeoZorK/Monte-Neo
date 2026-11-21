"""Strategy Lab idea.

Not investment advice. Parameters are fixed BEFORE any data is looked at; see card.md.
"""

import pandas as pd

META = {"kind": "returns", "title": "Funding carry: long spot / short perpetual basket", "family": "carry",
        "data": {"spot": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"], "perp": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"],
                 "fund": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]},
        "params": {"lookback": 7, "threshold": 0.0002}, "grid": {"lookback": [3, 7, 14], "threshold": [0.0001, 0.0002, 0.0004]}}
SWITCH_COST = 25e-4  # one-way, both legs: spot 10 bps + perp 5 bps commission, 5 + 5 bps slippage
MARGIN = 0.25        # capital = spot notional + 25 % posted as perp margin


def returns(data: dict, lookback: int = 7, threshold: float = 0.0002) -> pd.Series:
    """Hold spot long + perp short in an asset while its trailing mean DAILY funding (decided at close t-1) exceeds threshold.

    Daily P&L per held asset = spot return - perp return + funding received that day - switching cost. Equal weight over the
    basket's assets that are listed on both markets; return is on capital (1 + MARGIN).
    """
    cols = {}
    for sym in data["spot"]:
        s = data["spot"][sym].set_index("timestamp")["close"]
        p = data["perp"][sym].set_index("timestamp")["close"]
        f = data["fund"][sym].set_index("timestamp")["funding"]
        idx = s.index.intersection(p.index)
        basis = s.loc[idx].pct_change() - p.loc[idx].pct_change()
        fund = f.reindex(idx).fillna(0.0)
        on = (fund.rolling(lookback).mean().shift(1) > threshold).astype(float)  # known at the previous close
        cost = on.diff().abs().fillna(on) * SWITCH_COST
        cols[sym] = on * (basis + fund) - cost
    table = pd.DataFrame(cols)
    listed = table.notna().sum(axis=1).clip(lower=1)
    return (table.fillna(0.0).sum(axis=1) / listed / (1.0 + MARGIN)).rename("return")
