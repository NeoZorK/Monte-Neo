"""Strategy Lab round 3.

Not investment advice. Parameters are fixed BEFORE any data is looked at (pre-registered, see card.md).
"""

import pandas as pd

META = {"kind": "alpha", "round": 3, "title": "Betting against beta: long low-beta, short high-beta coins (BTC-hedged)", "family": "cross_section",
        "universe": ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","LTCUSDT","TRXUSDT","LINKUSDT","XLMUSDT","ETCUSDT","NEOUSDT","ATOMUSDT","DOGEUSDT","BCHUSDT","SOLUSDT","DOTUSDT","AVAXUSDT","UNIUSDT"], "portfolio": "long_short", "hedge_btc": True,
        "params": {"beta_window": 90, "horizon": 7}, "grid": {"beta_window": [60, 90, 150]}, "horizon": 7}

def scores(panel: dict[str, pd.DataFrame], beta_window: int = 90) -> pd.DataFrame:
    """Score = minus the trailing beta of the coin to BTC (low beta ranks high)."""
    close = pd.DataFrame({s: d.set_index("timestamp")["close"] for s, d in panel.items()})
    ret = close.pct_change()
    btc = ret["BTCUSDT"]
    rel = (-ret.rolling(beta_window).cov(btc).div(btc.rolling(beta_window).var(), axis=0)).drop(columns="BTCUSDT")
    out = rel.stack().rename("score").reset_index()
    out.columns = ["timestamp", "symbol", "score"]
    return out.replace([float("inf"), float("-inf")], float("nan")).dropna().sort_values(["timestamp", "symbol"]).reset_index(drop=True)
