"""Strategy Lab round 2.

Not investment advice. Parameters are fixed BEFORE any data is looked at (pre-registered, see card.md).
"""

import pandas as pd

UNIVERSE = ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","LTCUSDT","TRXUSDT","LINKUSDT","XLMUSDT","ETCUSDT","NEOUSDT","ATOMUSDT","DOGEUSDT","BCHUSDT","SOLUSDT","DOTUSDT","AVAXUSDT","UNIUSDT"]
META = {"kind": "alpha", "round": 2, "title": "BTC-neutral residual momentum, long-short, 18 coins", "family": "market_neutral",
        "universe": UNIVERSE, "portfolio": "long_short", "hedge_btc": True,
        "params": {"lookback": 60, "skip": 1, "beta_window": 90, "horizon": 7}, "grid": {"lookback": [30, 60, 90]}, "horizon": 7}


def scores(panel: dict[str, pd.DataFrame], lookback: int = 60, skip: int = 1, beta_window: int = 90) -> pd.DataFrame:
    """Score = coin return over [t-skip-lookback, t-skip] minus beta times the BTC return over the same span (beta: trailing, known at t)."""
    close = pd.DataFrame({s: d.set_index("timestamp")["close"] for s, d in panel.items()})
    ret = close.pct_change()
    btc = ret["BTCUSDT"]
    beta = ret.rolling(beta_window).cov(btc).div(btc.rolling(beta_window).var(), axis=0)
    span = close.shift(skip) / close.shift(skip + lookback) - 1.0
    resid = span.sub(beta.mul(span["BTCUSDT"], axis=0))
    out = resid.drop(columns="BTCUSDT").stack().rename("score").reset_index()
    out.columns = ["timestamp", "symbol", "score"]
    return out.dropna().sort_values(["timestamp", "symbol"]).reset_index(drop=True)
