"""Strategy Lab round 2.

Not investment advice. Parameters are fixed BEFORE any data is looked at (pre-registered, see card.md).
"""

import pandas as pd

UNIVERSE = ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","LTCUSDT","TRXUSDT","LINKUSDT","XLMUSDT","ETCUSDT","NEOUSDT","ATOMUSDT","DOGEUSDT","BCHUSDT","SOLUSDT","DOTUSDT","AVAXUSDT","UNIUSDT"]
META = {"kind": "alpha", "round": 2, "title": "Trend versus market: long-short on distance above SMA relative to BTC", "family": "market_neutral",
        "universe": UNIVERSE, "portfolio": "long_short", "hedge_btc": True,
        "params": {"sma": 100, "horizon": 7}, "grid": {"sma": [50, 100, 150]}, "horizon": 7}


def scores(panel: dict[str, pd.DataFrame], sma: int = 100) -> pd.DataFrame:
    """Score = log(close / SMA) of the coin minus the same quantity for BTC: is the coin trending stronger than the market?"""
    import numpy as np

    close = pd.DataFrame({s: d.set_index("timestamp")["close"] for s, d in panel.items()})
    dist = np.log(close / close.rolling(sma).mean())
    rel = dist.sub(dist["BTCUSDT"], axis=0).drop(columns="BTCUSDT")
    out = rel.stack().rename("score").reset_index()
    out.columns = ["timestamp", "symbol", "score"]
    return out.dropna().sort_values(["timestamp", "symbol"]).reset_index(drop=True)
