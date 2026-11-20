"""Strategy Lab search candidate f02299eebaba6959 (batch 4). Not investment advice. Spec fixed by the committed batch file."""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
import signals  # noqa: E402

SPEC = {"family": "comp_VH", "params": {"parts": ["V", "H"]}, "sign": 1, "composite": [{"family": "tstrend", "params": {"lookback": 60, "vol_window": 30}, "sign": 1}, {"family": "hi52", "params": {"window": 365, "skip": 0}, "sign": 1}], "horizon": 3, "top_k": 30}
META = {"kind": "alpha", "round": 4, "title": "Search candidate f02299ee: comp_VH {'parts': ['V', 'H']} sign 1, top 30 liquid coins",
        "family": "search_comp_VH", "universe": json.loads((Path(__file__).resolve().parents[1] / "_common" / "wide_universe.json").read_text()),
        "portfolio": "long_short", "hedge_btc": True, "params": {}, "grid": {}, "horizon": 3}


def scores(panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    close = pd.DataFrame({s: d.set_index("timestamp")["close"] for s, d in panel.items()}).sort_index()
    volume = pd.DataFrame({s: d.set_index("timestamp")["volume"] for s, d in panel.items()}).sort_index()
    return signals.long_form(signals.score(close, volume, SPEC))
