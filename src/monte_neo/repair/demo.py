"""``monte-neo repair --demo``: three strategies, three honest outcomes, no files needed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LEAK = '''import numpy as np


def signal(df):
    """Reads tomorrow's close: shift(-1)."""
    return np.sign(df["close"].shift(-1) / df["close"] - 1).fillna(0)
'''

FLICKER = '''import numpy as np


def signal(df):
    """A real 40-day trend signal, but noisy: it flips almost every day and pays costs every time."""
    mom = df["close"].pct_change(40)
    noise = np.random.default_rng(1).normal(0, 0.06, len(df))
    return np.sign((mom + noise).fillna(0))
'''

UNSEEDED = '''import numpy as np


def signal(df):
    """A different answer on every run: nothing can be verified, so nothing can be repaired."""
    return np.random.default_rng().choice([-1.0, 1.0], len(df))
'''


def trending_market(seed: int = 1, n: int = 3000) -> pd.DataFrame:
    """Daily bars whose drift switches sign every 150 days: slow trends under noise."""
    rng = np.random.default_rng(seed)
    drift = np.repeat(rng.choice([-1.0, 1.0], n // 150 + 1) * 0.0012, 150)[:n]
    r = drift + rng.normal(0, 0.01, n)
    close = 100 * np.exp(np.cumsum(r))
    op = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"timestamp": pd.date_range("2012-01-01", periods=n, freq="D"), "open": op,
                         "high": np.maximum(op, close) * 1.001, "low": np.minimum(op, close) * 0.999,
                         "close": close, "volume": 1e6})


def run_demo(out_dir: str | Path) -> list[tuple[str, dict[str, Any]]]:
    """Repair the three demo strategies; returns ``[(name, repair-report/1)]``."""
    from monte_neo.backtest import synthetic_ohlcv
    from monte_neo.repair.run import repair_strategy
    from monte_neo.verify import model_from_costs

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    market = trending_market()
    cases = (
        ("leak", LEAK, synthetic_ohlcv(2000, seed=3), None),
        ("flicker", FLICKER, market, model_from_costs(commission_bps=10, slippage_bps=10, n_bars=len(market))),
        ("unseeded", UNSEEDED, synthetic_ohlcv(2000, seed=3), None),
    )
    results = []
    for name, source, data, model in cases:
        path = out / f"{name}.py"
        path.write_text(source, encoding="utf-8")
        prices = out / f"{name}.csv"  # repaired from the file, so a recheck reads exactly the same data
        data.to_csv(prices, index=False)
        results.append((name, repair_strategy(str(prices), str(path), out_dir=out / name, model=model)))
    return results


__all__ = ["run_demo", "trending_market"]
