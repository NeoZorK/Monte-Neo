"""Strategy Lab round 5: arbitrage of the law of one price between spot and perpetual.

Not investment advice. Parameters are fixed BEFORE any data is looked at; see card.md.
"""

import numpy as np
import pandas as pd

COINS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "LTCUSDT"]
META = {"kind": "returns", "round": 5, "title": "Basis reversion: long spot, short perpetual when the perpetual premium is stretched",
        "family": "basis_arbitrage", "structure": "MN",
        "data": {"spot": COINS, "perp": COINS, "fund": COINS},
        "params": {"window": 60, "entry": 2.0, "exit": 0.5}, "grid": {"window": [30, 60, 90], "entry": [1.5, 2.0, 2.5]}}
COST_BPS = 15.0  # per side per leg: 10 commission + 5 slippage
MARGIN = 0.25  # perp margin held beside the spot notional: capital per unit of position = 1 + MARGIN


def _coin(spot: pd.Series, perp: pd.Series, fund: pd.Series, window: int, entry: float, exit: float) -> pd.DataFrame:
    """Per-coin daily book: in position (long spot, short perp) from the close after z > entry until z < exit."""
    idx = spot.index.intersection(perp.index)
    s, p = spot.loc[idx], perp.loc[idx]
    premium = np.log(p / s)
    mu, sd = premium.rolling(window).mean(), premium.rolling(window).std()
    z = ((premium - mu) / sd).to_numpy()
    held = np.zeros(len(z))
    cur = 0.0
    for i, zi in enumerate(z):  # path-dependent state machine
        if np.isfinite(zi):
            if cur == 0.0 and zi > entry:
                cur = 1.0
            elif cur == 1.0 and zi < exit:
                cur = 0.0
        held[i] = cur
    pos = np.concatenate([[0.0], held[:-1]])  # decided at close t-1, held over bar t
    rs, rp = s.pct_change().fillna(0.0).to_numpy(), p.pct_change().fillna(0.0).to_numpy()
    f = fund.reindex(idx).fillna(0.0).to_numpy()  # daily funding, paid by longs: the short perp receives it
    turn = np.abs(np.diff(pos, prepend=0.0)) * 2.0  # two legs change together
    net = (pos * (rs - rp + f) - turn * COST_BPS / 1e4) / (1.0 + MARGIN)
    return pd.DataFrame({"ret": net, "pos": pos}, index=idx)


def returns(data: dict, window: int = 60, entry: float = 2.0, exit: float = 0.5) -> pd.Series:
    """Daily net return on capital: equal capital per coin; a coin out of position earns nothing (cash)."""
    books = []
    for c in COINS:
        if c not in data["spot"] or c not in data["perp"]:
            continue
        sp = data["spot"][c].set_index("timestamp")["close"]
        pp = data["perp"][c].set_index("timestamp")["close"]
        fu = data["fund"][c].set_index("timestamp")["funding"] if c in data.get("fund", {}) else pd.Series(dtype=float)
        books.append(_coin(sp, pp, fu, window, entry, exit)["ret"].rename(c))
    panel = pd.concat(books, axis=1).sort_index()
    live = panel.notna().sum(axis=1).replace(0, np.nan)
    return (panel.fillna(0.0).sum(axis=1) / live).fillna(0.0).rename("return")
