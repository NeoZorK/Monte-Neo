"""Strategy Lab search candidate b525736deed1c8b1 (batch 2). Not investment advice. Spec fixed by the committed batch file."""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
import signals  # noqa: E402

SPEC = {"family": "comp_VLH", "params": {"parts": ["V", "L", "H"]}, "sign": 1, "composite": [{"family": "tstrend", "params": {"lookback": 60, "vol_window": 30}, "sign": 1}, {"family": "lowvol2", "params": {"window": 45}, "sign": -1}, {"family": "hi52", "params": {"window": 365, "skip": 0}, "sign": 1}], "horizon": 14, "top_k": 60}
META = {"kind": "alpha", "round": 4, "title": "Search candidate b525736d: comp_VLH {'parts': ['V', 'L', 'H']} sign 1, top 60 liquid coins",
        "family": "search_comp_VLH", "universe": json.loads((Path(__file__).resolve().parents[1] / "_common" / "wide_universe.json").read_text()),
        "portfolio": "long_short", "hedge_btc": True, "params": {}, "grid": {}, "horizon": 14}


def scores(panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    close = pd.DataFrame({s: d.set_index("timestamp")["close"] for s, d in panel.items()}).sort_index()
    volume = pd.DataFrame({s: d.set_index("timestamp")["volume"] for s, d in panel.items()}).sort_index()
    return signals.long_form(signals.score(close, volume, SPEC))
