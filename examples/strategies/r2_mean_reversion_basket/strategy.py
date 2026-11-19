"""Strategy Lab round 2 (idea: Claude Sonnet 5.5; process and verification: Rostyslav Shcherbyna).

Not investment advice. Parameters are fixed BEFORE any data is looked at (pre-registered, see card.md).
"""

import pandas as pd

UNIVERSE = ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","LTCUSDT","TRXUSDT","LINKUSDT","XLMUSDT","ETCUSDT","NEOUSDT","ATOMUSDT","DOGEUSDT","BCHUSDT","SOLUSDT","DOTUSDT","AVAXUSDT","UNIUSDT"]
META = {"kind": "alpha", "round": 2, "title": "Short-term mean reversion basket, long-short, 18 coins", "family": "mean_reversion",
        "universe": UNIVERSE, "portfolio": "long_short", "hedge_btc": True,
        "params": {"lookback": 5, "horizon": 3}, "grid": {"lookback": [3, 5, 10]}, "horizon": 3}


def scores(panel: dict[str, pd.DataFrame], lookback: int = 5) -> pd.DataFrame:
    """Score = minus the coin's return over the last `lookback` closes (losers are expected to bounce, winners to fade)."""
    rows = []
    for sym, df in panel.items():
        c = df.set_index("timestamp")["close"]
        s = -(c / c.shift(lookback) - 1.0)
        rows.append(pd.DataFrame({"timestamp": s.index, "symbol": sym, "score": s.to_numpy()}))
    return pd.concat(rows).dropna().sort_values(["timestamp", "symbol"]).reset_index(drop=True)
