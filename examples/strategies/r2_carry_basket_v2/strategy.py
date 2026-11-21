"""Strategy Lab round 2.

Not investment advice. Parameters are fixed BEFORE any data is looked at (pre-registered, see card.md).
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
from binance_costs import side_frac  # noqa: E402

SYMS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOGEUSDT", "DOTUSDT", "AVAXUSDT", "ATOMUSDT"]
META = {"kind": "returns", "round": 2, "title": "Funding carry v2: long spot / short perpetual, 12 coins, per-coin costs", "family": "carry",
        "data": {"spot": SYMS, "perp": SYMS, "fund": SYMS},
        "params": {"lookback": 14, "threshold": 0.0002}, "grid": {"lookback": [7, 14, 30]}}
MARGIN = 0.25  # capital = spot notional + 25 % posted as perp margin


def returns(data: dict, lookback: int = 14, threshold: float = 0.0002, cost_mult: float = 1.0) -> pd.Series:
    """Hold spot long + perp short in a coin while its trailing mean DAILY funding (decided at close t-1) exceeds `threshold`.

    Daily P&L per held coin = spot return - perp return + funding received - switching cost (spot AND perp side, per-coin fee+spread).
    Equal weight over coins listed on both markets; return on capital (1 + MARGIN). Funding is the actual published rate.
    """
    cols = {}
    for sym in data["spot"]:
        if sym not in data["perp"] or sym not in data["fund"]:
            continue
        s = data["spot"][sym].set_index("timestamp")["close"]
        p = data["perp"][sym].set_index("timestamp")["close"]
        f = data["fund"][sym].set_index("timestamp")["funding"]
        idx = s.index.intersection(p.index)
        basis = s.loc[idx].pct_change() - p.loc[idx].pct_change()
        fund = f.reindex(idx).fillna(0.0)
        on = (fund.rolling(lookback).mean().shift(1) > threshold).astype(float)
        one_way = side_frac(sym, "spot", cost_mult) + side_frac(sym, "perp", cost_mult)
        cols[sym] = on * (basis + fund) - on.diff().abs().fillna(on) * one_way
    table = pd.DataFrame(cols)
    listed = table.notna().sum(axis=1).clip(lower=1)
    return (table.fillna(0.0).sum(axis=1) / listed / (1.0 + MARGIN)).rename("return")
