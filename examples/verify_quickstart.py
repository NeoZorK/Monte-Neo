"""Verifier quickstart: a leaky strategy is rejected, a causal one is not accused.

Run: uv run python examples/verify_quickstart.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import verify_strategy


def leaky(df: pd.DataFrame) -> np.ndarray:
    """Typical agent bug: tomorrow's close decides today's position."""
    return np.sign(df["close"].shift(-1) - df["close"]).to_numpy()


def causal(df: pd.DataFrame) -> np.ndarray:
    """SMA crossover that only uses rows <= t."""
    fast = df["close"].rolling(20).mean()
    slow = df["close"].rolling(80).mean()
    return np.where(fast > slow, 1, 0)


def main() -> None:
    df = synthetic_ohlcv(3000, seed=1)
    for name, fn, src in (
        ("leaky", leaky, "x = df['close'].shift(-1)"),
        ("causal", causal, None),
    ):
        report = verify_strategy(df, signal_fn=fn, source=src, n_trials=10)
        print(f"{name}: {report['verdict']}  certificate {report['certificate_id']}")
        for check in report["checks"]:
            if check["status"] in ("fail", "warn"):
                print(f"  {check['id']:24s} {check['category']:11s} {check['status']:5s} {check['summary']}")
        if report["next_actions"]:
            print(f"  -> {report['next_actions'][0]}")


if __name__ == "__main__":
    main()
