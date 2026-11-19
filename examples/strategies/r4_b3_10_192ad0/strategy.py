"""Strategy Lab search candidate 192ad0ce97fae8f8 (batch 3). Not investment advice. Spec fixed by the committed batch file."""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
import signals  # noqa: E402

SPEC = {"family": "resmom", "params": {"lookback": 30, "beta_window": 60}, "sign": 1, "horizon": 7, "top_k": 60}
META = {"kind": "alpha", "round": 4, "title": "Search candidate 192ad0ce: resmom {'lookback': 30, 'beta_window': 60} sign 1, top 60 liquid coins",
        "family": "search_resmom", "universe": json.loads((Path(__file__).resolve().parents[1] / "_common" / "wide_universe.json").read_text()),
        "portfolio": "long_short", "hedge_btc": True, "params": {}, "grid": {}, "horizon": 7}


def scores(panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    close = pd.DataFrame({s: d.set_index("timestamp")["close"] for s, d in panel.items()}).sort_index()
    volume = pd.DataFrame({s: d.set_index("timestamp")["volume"] for s, d in panel.items()}).sort_index()
    return signals.long_form(signals.score(close, volume, SPEC))
