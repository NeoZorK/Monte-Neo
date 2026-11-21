"""Strategy Lab round 3.

Not investment advice. Parameters are fixed BEFORE any data is looked at (pre-registered, see card.md).
"""

import pandas as pd

META = {"kind": "alpha", "round": 3, "title": "High-volume reversal: fade the 5-day move, stronger when volume is unusual (BTC-hedged)", "family": "mean_reversion",
        "universe": ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","LTCUSDT","TRXUSDT","LINKUSDT","XLMUSDT","ETCUSDT","NEOUSDT","ATOMUSDT","DOGEUSDT","BCHUSDT","SOLUSDT","DOTUSDT","AVAXUSDT","UNIUSDT"], "portfolio": "long_short", "hedge_btc": True,
        "params": {"lookback": 5, "volume_window": 60, "horizon": 5}, "grid": {"lookback": [3, 5, 10]}, "horizon": 5}

def scores(panel: dict[str, pd.DataFrame], lookback: int = 5, volume_window: int = 60) -> pd.DataFrame:
    """Score = minus the lookback return times the ratio of recent to long-run dollar volume (volume-confirmed moves reverse less, quiet moves more: sign fixed a priori as price pressure from liquidity demand)."""
    close = pd.DataFrame({s: d.set_index("timestamp")["close"] for s, d in panel.items()})
    vol = pd.DataFrame({s: d.set_index("timestamp")["volume"] * d.set_index("timestamp")["close"] for s, d in panel.items()})
    ratio = vol.rolling(lookback).mean() / vol.rolling(volume_window).mean()
    rel = (-(close / close.shift(lookback) - 1.0) * ratio).drop(columns="BTCUSDT")
    out = rel.stack().rename("score").reset_index()
    out.columns = ["timestamp", "symbol", "score"]
    return out.replace([float("inf"), float("-inf")], float("nan")).dropna().sort_values(["timestamp", "symbol"]).reset_index(drop=True)
