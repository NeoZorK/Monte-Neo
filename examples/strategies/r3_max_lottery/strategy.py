"""Strategy Lab round 3 (idea: Claude Sonnet 5.5; process and verification: Rostyslav Shcherbyna).

Not investment advice. Parameters are fixed BEFORE any data is looked at (pre-registered, see card.md).
"""

import pandas as pd

META = {"kind": "alpha", "round": 3, "title": "Lottery effect: short coins with the largest recent daily jump, long the rest (BTC-hedged)", "family": "cross_section",
        "universe": ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","LTCUSDT","TRXUSDT","LINKUSDT","XLMUSDT","ETCUSDT","NEOUSDT","ATOMUSDT","DOGEUSDT","BCHUSDT","SOLUSDT","DOTUSDT","AVAXUSDT","UNIUSDT"], "portfolio": "long_short", "hedge_btc": True,
        "params": {"window": 30, "horizon": 7}, "grid": {"window": [14, 30, 60]}, "horizon": 7}

def scores(panel: dict[str, pd.DataFrame], window: int = 30) -> pd.DataFrame:
    """Score = minus the largest daily return of the last `window` days (Bali, Cakici and Whitelaw MAX effect)."""
    close = pd.DataFrame({s: d.set_index("timestamp")["close"] for s, d in panel.items()})
    rel = (-close.pct_change().rolling(window).max()).drop(columns="BTCUSDT")
    out = rel.stack().rename("score").reset_index()
    out.columns = ["timestamp", "symbol", "score"]
    return out.replace([float("inf"), float("-inf")], float("nan")).dropna().sort_values(["timestamp", "symbol"]).reset_index(drop=True)
