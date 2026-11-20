"""Strategy Lab idea (author of the idea: Claude Sonnet 5.5; process and verification: Rostyslav Shcherbyna).

Not investment advice. Parameters are fixed BEFORE any data is looked at; see card.md.
"""

import pandas as pd

META = {"kind": "alpha", "title": "Cross-sectional momentum, 10 USDT spot coins", "family": "cross_section",
        "universe": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOGEUSDT", "TRXUSDT"],
        "params": {"lookback": 60, "skip": 1, "horizon": 7}, "grid": {"lookback": [30, 60, 90]}, "horizon": 7}


def scores(panel: dict[str, pd.DataFrame], lookback: int = 60, skip: int = 1) -> pd.DataFrame:
    """Score at close t = return from t-skip-lookback to t-skip. Higher score = expected to outperform over the next bars."""
    rows = []
    for sym, df in panel.items():
        close = df.set_index("timestamp")["close"]
        s = close.shift(skip) / close.shift(skip + lookback) - 1.0
        rows.append(pd.DataFrame({"timestamp": s.index, "symbol": sym, "score": s.to_numpy()}))
    out = pd.concat(rows).dropna()
    return out.sort_values(["timestamp", "symbol"]).reset_index(drop=True)
