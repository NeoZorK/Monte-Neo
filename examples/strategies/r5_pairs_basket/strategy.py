"""Strategy Lab round 5: a basket of rolling-hedge pairs (perpetuals), so one broken relationship is not the whole book.

Not investment advice. Parameters are fixed BEFORE any data is looked at; see card.md.
"""

import numpy as np
import pandas as pd

PAIRS = [("ETHUSDT", "BTCUSDT"), ("SOLUSDT", "ETHUSDT"), ("BNBUSDT", "BTCUSDT"), ("LTCUSDT", "BTCUSDT"),
         ("LINKUSDT", "ETHUSDT"), ("ADAUSDT", "XRPUSDT")]
COINS = sorted({c for p in PAIRS for c in p})
META = {"kind": "returns", "round": 5, "title": "Pairs basket: six rolling-hedge spreads on perpetuals, equal risk",
        "family": "pairs", "structure": "MN", "data": {"perp": COINS, "fund": COINS},
        "params": {"window": 90, "entry": 2.0, "exit": 0.5, "stop": 4.0},
        "grid": {"window": [60, 90, 120], "entry": [1.5, 2.0, 2.5]}}
COST_BPS = 15.0  # per side per leg


def _pair(y: pd.Series, x: pd.Series, fy: pd.Series, fx: pd.Series, window: int, entry: float, exit: float, stop: float) -> pd.Series:
    idx = y.index.intersection(x.index)
    ly, lx = np.log(y.loc[idx]), np.log(x.loc[idx])
    beta = (ly.rolling(window).cov(lx) / lx.rolling(window).var())
    spread = ly - beta * lx
    z = ((spread - spread.rolling(window).mean()) / spread.rolling(window).std()).to_numpy()
    side = np.zeros(len(z))
    cur = 0.0
    for i, zi in enumerate(z):
        if np.isfinite(zi):
            if cur == 0.0 and entry < abs(zi) < stop:
                cur = -np.sign(zi)
            elif cur != 0.0 and (abs(zi) < exit or abs(zi) > stop):  # the stop closes a spread that keeps running away
                cur = 0.0
        side[i] = cur
    b = np.nan_to_num(beta.to_numpy())
    scale = 1.0 / (1.0 + np.abs(b))  # gross exposure 1 per pair
    qy = np.concatenate([[0.0], (side * scale)[:-1]])
    qx = np.concatenate([[0.0], (-side * b * scale)[:-1]])
    dy, dx = ly.diff().fillna(0.0).to_numpy(), lx.diff().fillna(0.0).to_numpy()
    f_y, f_x = fy.reindex(idx).fillna(0.0).to_numpy(), fx.reindex(idx).fillna(0.0).to_numpy()
    turn = np.abs(np.diff(qy, prepend=0.0)) + np.abs(np.diff(qx, prepend=0.0))
    net = qy * dy + qx * dx - (qy * f_y + qx * f_x) - turn * COST_BPS / 1e4
    return pd.Series(net, index=idx)


def returns(data: dict, window: int = 90, entry: float = 2.0, exit: float = 0.5, stop: float = 4.0) -> pd.Series:
    """Daily net return: the mean of the pairs available that day (each pair at gross exposure 1)."""
    def close(c: str) -> pd.Series:
        return data["perp"][c].set_index("timestamp")["close"]

    def fund(c: str) -> pd.Series:
        return data["fund"][c].set_index("timestamp")["funding"] if c in data.get("fund", {}) else pd.Series(dtype=float)

    legs = [_pair(close(a), close(b), fund(a), fund(b), window, entry, exit, stop).rename(f"{a}/{b}")
            for a, b in PAIRS if a in data["perp"] and b in data["perp"]]
    panel = pd.concat(legs, axis=1).sort_index()
    return panel.mean(axis=1, skipna=True).fillna(0.0).rename("return")
