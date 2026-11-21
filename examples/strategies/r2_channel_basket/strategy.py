"""Strategy Lab round 2.

Not investment advice. Parameters are fixed BEFORE any data is looked at (pre-registered, see card.md).
"""

import pandas as pd

UNIVERSE = ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","LTCUSDT","TRXUSDT","LINKUSDT","XLMUSDT","ETCUSDT","NEOUSDT","ATOMUSDT","DOGEUSDT","BCHUSDT","SOLUSDT","DOTUSDT","AVAXUSDT","UNIUSDT"]
META = {"kind": "alpha", "round": 2, "title": "Donchian channel position basket, 18 coins", "family": "trend_basket",
        "universe": UNIVERSE, "portfolio": "long_flat", "hedge_btc": False,
        "params": {"window": 55, "horizon": 7}, "grid": {"window": [40, 55, 80]}, "horizon": 7}


def scores(panel: dict[str, pd.DataFrame], window: int = 55) -> pd.DataFrame:
    """Score = where the close sits inside the channel of the previous `window` closes, centred at 0 (above 0 = upper half)."""
    rows = []
    for sym, df in panel.items():
        c = df.set_index("timestamp")["close"]
        hi, lo = c.shift(1).rolling(window).max(), c.shift(1).rolling(window).min()
        s = (c - lo) / (hi - lo) - 0.5
        rows.append(pd.DataFrame({"timestamp": s.index, "symbol": sym, "score": s.to_numpy()}))
    return pd.concat(rows).replace([float("inf"), float("-inf")], float("nan")).dropna().sort_values(["timestamp", "symbol"]).reset_index(drop=True)
