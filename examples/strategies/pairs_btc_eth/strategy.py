"""Strategy Lab idea (author of the idea: Claude Sonnet 5.5; process and verification: Rostyslav Shcherbyna).

Not investment advice. Parameters are fixed BEFORE any data is looked at; see card.md.
"""

import numpy as np
import pandas as pd

META = {"kind": "returns", "title": "Pairs: ETH vs BTC log-price spread (perpetuals)", "family": "pairs", "pair": True,
        "data": {"perp": ["ETHUSDT", "BTCUSDT"], "fund": ["ETHUSDT", "BTCUSDT"]},
        "params": {"window": 90, "entry": 2.0, "exit": 0.5}, "grid": {"window": [60, 90, 120], "entry": [1.5, 2.0, 2.5]}}
COST_BPS = 15.0  # per side per leg: 10 commission + 5 slippage


def _book(prices: pd.DataFrame, window: int, entry: float, exit: float) -> dict[str, np.ndarray]:
    """Quantities (log-notional, gross exposure 1) held over each bar, decided at the PREVIOUS close."""
    ly, lx = np.log(prices["leg1"].to_numpy(float)), np.log(prices["leg2"].to_numpy(float))
    y, x = pd.Series(ly), pd.Series(lx)
    beta = (y.rolling(window).cov(x) / x.rolling(window).var()).to_numpy()
    alpha = (y.rolling(window).mean() - beta * x.rolling(window).mean()).to_numpy()
    spread = pd.Series(ly - beta * lx - alpha)
    z = (spread / spread.rolling(window).std()).to_numpy()
    side = np.zeros(len(z))
    cur = 0.0
    for i, zi in enumerate(z):  # path-dependent state machine; ~3000 bars
        if np.isfinite(zi):
            if cur == 0.0 and zi > entry:
                cur = -1.0
            elif cur == 0.0 and zi < -entry:
                cur = 1.0
            elif cur != 0.0 and abs(zi) < exit:
                cur = 0.0
        side[i] = cur
    scale = 1.0 / (1.0 + np.abs(np.nan_to_num(beta)))
    qty_y = np.zeros(len(z))
    qty_x = np.zeros(len(z))
    qty_y[1:] = (side * scale)[:-1]  # decided at close t-1, held over bar t
    qty_x[1:] = (-side * np.nan_to_num(beta) * scale)[:-1]
    return {"qty_y": qty_y, "qty_x": qty_x, "ly": ly, "lx": lx}


def _gross(b: dict[str, np.ndarray]) -> np.ndarray:
    dy, dx = np.diff(b["ly"], prepend=b["ly"][0]), np.diff(b["lx"], prepend=b["lx"][0])
    return b["qty_y"] * dy + b["qty_x"] * dx


def _cost(b: dict[str, np.ndarray]) -> np.ndarray:
    turn = np.abs(np.diff(b["qty_y"], prepend=0.0)) + np.abs(np.diff(b["qty_x"], prepend=0.0))
    return turn * COST_BPS / 1e4


def pnl(prices: pd.DataFrame, window: int = 90, entry: float = 2.0, exit: float = 0.5) -> np.ndarray:
    """Net per-bar returns on random-walk or real prices (columns leg1, leg2): used by monte-neo verify --null-test."""
    b = _book(prices, window, entry, exit)
    return np.nan_to_num(_gross(b) - _cost(b))


def returns(data: dict, window: int = 90, entry: float = 2.0, exit: float = 0.5) -> pd.Series:
    """Daily net return: legs earn their price change, costs on every quantity change, funding paid by longs and received by shorts."""
    py, px = data["perp"]["ETHUSDT"].set_index("timestamp")["close"], data["perp"]["BTCUSDT"].set_index("timestamp")["close"]
    idx = py.index.intersection(px.index)
    prices = pd.DataFrame({"leg1": py.loc[idx].to_numpy(), "leg2": px.loc[idx].to_numpy()}, index=idx)
    b = _book(prices, window, entry, exit)
    fy = data["fund"]["ETHUSDT"].set_index("timestamp")["funding"].reindex(idx).fillna(0.0).to_numpy()
    fx = data["fund"]["BTCUSDT"].set_index("timestamp")["funding"].reindex(idx).fillna(0.0).to_numpy()
    funding = -(b["qty_y"] * fy + b["qty_x"] * fx)  # a long pays a positive funding rate
    net = _gross(b) - _cost(b) + funding
    return pd.Series(np.nan_to_num(net), index=idx, name="return")


def legs(data: dict, window: int = 90, entry: float = 2.0, exit: float = 0.5) -> pd.DataFrame:
    """Leg table for monte-neo verify --legs (date, px_y, px_x, qty_y, qty_x, reported_return = gross leg P&L)."""
    py, px = data["perp"]["ETHUSDT"].set_index("timestamp")["close"], data["perp"]["BTCUSDT"].set_index("timestamp")["close"]
    idx = py.index.intersection(px.index)
    prices = pd.DataFrame({"leg1": py.loc[idx].to_numpy(), "leg2": px.loc[idx].to_numpy()}, index=idx)
    b = _book(prices, window, entry, exit)
    out = pd.DataFrame({"date": idx.tz_localize(None), "px_y": prices["leg1"].to_numpy(), "px_x": prices["leg2"].to_numpy(),
                        "qty_y": b["qty_y"], "qty_x": b["qty_x"], "reported_return": _gross(b)})
    return out.iloc[window + 1:]
