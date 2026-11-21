"""Strategy Lab round 3.

Not investment advice. Parameters are fixed BEFORE any data is looked at (pre-registered, see card.md).
"""

import pandas as pd

META = {"kind": "alpha", "round": 3, "title": "Long-term reversal: fade the 180-day loser/winner skipping the last month (BTC-hedged)", "family": "cross_section",
        "universe": ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","LTCUSDT","TRXUSDT","LINKUSDT","XLMUSDT","ETCUSDT","NEOUSDT","ATOMUSDT","DOGEUSDT","BCHUSDT","SOLUSDT","DOTUSDT","AVAXUSDT","UNIUSDT"], "portfolio": "long_short", "hedge_btc": True,
        "params": {"lookback": 180, "skip": 30, "horizon": 14}, "grid": {"lookback": [120, 180, 270]}, "horizon": 14}

def scores(panel: dict[str, pd.DataFrame], lookback: int = 180, skip: int = 30) -> pd.DataFrame:
    """Score = minus the return from t-skip-lookback to t-skip (De Bondt and Thaler style long-term reversal)."""
    close = pd.DataFrame({s: d.set_index("timestamp")["close"] for s, d in panel.items()})
    rel = (-(close.shift(skip) / close.shift(skip + lookback) - 1.0)).drop(columns="BTCUSDT")
    out = rel.stack().rename("score").reset_index()
    out.columns = ["timestamp", "symbol", "score"]
    return out.replace([float("inf"), float("-inf")], float("nan")).dropna().sort_values(["timestamp", "symbol"]).reset_index(drop=True)
