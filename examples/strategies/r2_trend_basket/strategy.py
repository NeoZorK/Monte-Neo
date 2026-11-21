"""Strategy Lab round 2.

Not investment advice. Parameters are fixed BEFORE any data is looked at (pre-registered, see card.md).
"""

import pandas as pd

UNIVERSE = ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","LTCUSDT","TRXUSDT","LINKUSDT","XLMUSDT","ETCUSDT","NEOUSDT","ATOMUSDT","DOGEUSDT","BCHUSDT","SOLUSDT","DOTUSDT","AVAXUSDT","UNIUSDT"]
META = {"kind": "alpha", "round": 2, "title": "Trend basket: volatility-scaled time-series momentum, 18 coins", "family": "trend_basket",
        "universe": UNIVERSE, "portfolio": "long_flat", "hedge_btc": False,
        "params": {"lookback": 90, "vol_window": 30, "horizon": 7}, "grid": {"lookback": [60, 90, 120]}, "horizon": 7}


def scores(panel: dict[str, pd.DataFrame], lookback: int = 90, vol_window: int = 30) -> pd.DataFrame:
    """Score at close t = return over the last `lookback` closes divided by the trailing daily volatility (known at the close)."""
    rows = []
    for sym, df in panel.items():
        c = df.set_index("timestamp")["close"]
        s = (c / c.shift(lookback) - 1.0) / (c.pct_change().rolling(vol_window).std() * lookback**0.5)
        rows.append(pd.DataFrame({"timestamp": s.index, "symbol": sym, "score": s.to_numpy()}))
    return pd.concat(rows).replace([float("inf"), float("-inf")], float("nan")).dropna().sort_values(["timestamp", "symbol"]).reset_index(drop=True)
