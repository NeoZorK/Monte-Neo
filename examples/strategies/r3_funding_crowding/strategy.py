"""Strategy Lab round 3 (idea: Claude Sonnet 5.5; process and verification: Rostyslav Shcherbyna).

Not investment advice. Parameters are fixed BEFORE any data is looked at (pre-registered, see card.md).
"""

import pandas as pd

META = {"kind": "alpha", "round": 3, "title": "Funding crowding: short coins with the highest trailing perpetual funding, long the lowest (BTC-hedged)", "family": "carry_signal",
        "universe": ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","LTCUSDT","LINKUSDT","DOGEUSDT","DOTUSDT","AVAXUSDT","ATOMUSDT"], "portfolio": "long_short", "hedge_btc": True,
        "params": {"lookback": 14, "horizon": 7}, "grid": {"lookback": [7, 14, 30]}, "horizon": 7}

import os
from pathlib import Path

FUND = Path(os.environ.get("STRATEGY_LAB_HOME") or Path(__file__).resolve().parents[3] / "strategy_lab") / "data" / "processed"


def scores(panel: dict[str, pd.DataFrame], lookback: int = 14) -> pd.DataFrame:
    """Score = minus the trailing mean daily funding rate (crowded longs pay more: expected to lag). Directional signal, NOT a delta-neutral carry."""
    close = pd.DataFrame({s: d.set_index("timestamp")["close"] for s, d in panel.items()})
    cols = {}
    for s in close.columns:
        f = pd.read_parquet(FUND / f"fund_{s}_1d.parquet")
        f["timestamp"] = pd.to_datetime(f["timestamp"]).dt.tz_localize(None)
        cols[s] = f.set_index("timestamp")["funding"].reindex(close.index).rolling(lookback, min_periods=lookback // 2).mean()
    rel = (-pd.DataFrame(cols)).drop(columns="BTCUSDT")
    out = rel.stack().rename("score").reset_index()
    out.columns = ["timestamp", "symbol", "score"]
    return out.replace([float("inf"), float("-inf")], float("nan")).dropna().sort_values(["timestamp", "symbol"]).reset_index(drop=True)
