"""Strategy Lab search candidate 68ed02db743394dc (batch 3). Not investment advice. Spec fixed by the committed batch file."""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
import signals  # noqa: E402

SPEC = {"family": "comp_LHI", "params": {"parts": ["L", "H", "I"]}, "sign": 1, "composite": [{"family": "lowvol2", "params": {"window": 45}, "sign": -1}, {"family": "hi52", "params": {"window": 365, "skip": 0}, "sign": 1}, {"family": "illiq2", "params": {"window": 45, "agg": "mean"}, "sign": 1}], "horizon": 3, "top_k": 30}
META = {"kind": "alpha", "round": 4, "title": "Search candidate 68ed02db: comp_LHI {'parts': ['L', 'H', 'I']} sign 1, top 30 liquid coins",
        "family": "search_comp_LHI", "universe": json.loads((Path(__file__).resolve().parents[1] / "_common" / "wide_universe.json").read_text()),
        "portfolio": "long_short", "hedge_btc": True, "params": {}, "grid": {}, "horizon": 3}


def scores(panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    close = pd.DataFrame({s: d.set_index("timestamp")["close"] for s, d in panel.items()}).sort_index()
    volume = pd.DataFrame({s: d.set_index("timestamp")["volume"] for s, d in panel.items()}).sort_index()
    return signals.long_form(signals.score(close, volume, SPEC))
