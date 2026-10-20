"""Write legs.csv for one simulated pair: python make_legs.py legs_buggy.csv buggy  |  legs_fixed.csv fixed.

Columns: date, px_y, px_x, qty_y, qty_x, reported_return. The quantities are what was held over the bar ending at
``date`` (decided at the previous bar). ``reported_return`` is what the backtest booked: the wrong way for ``buggy``.
"""

import sys

import numpy as np
import pandas as pd

from monte_neo.verify.phantom import pair_pnl, random_walk_pair

out = sys.argv[1] if len(sys.argv) > 1 else "legs_buggy.csv"
mode = sys.argv[2] if len(sys.argv) > 2 else "buggy"
bars, window = 5000, 100
log_y, log_x = random_walk_pair(bars, 0.01, np.random.default_rng(20261015))
res = pair_pnl(log_y, log_x, window)
table = pd.DataFrame({
    "date": pd.date_range("2024-01-01", periods=bars, freq="h"),
    "px_y": np.exp(log_y), "px_x": np.exp(log_x), "qty_y": res["qty_y"], "qty_x": res["qty_x"],
    "reported_return": res["booked"] if mode == "buggy" else res["tradable"],
}).iloc[window + 1:]
table.to_csv(out, index=False, float_format="%.10g")
print("wrote", out, f"({len(table)} bars, {mode})")
