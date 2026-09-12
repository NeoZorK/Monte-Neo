"""Unit tests for Phase-2 race helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.core.race import fused_sma_sweep


def _toy_ohlcv(n: int = 800) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": rng.uniform(1, 5, n),
        }
    )


def test_fused_sma_sweep_runs():
    out = fused_sma_sweep(_toy_ohlcv(), combos=32)
    assert out["combos"] == 32
    assert out["device"] == "cpu_numba"
    assert len(out["rows"]) == 32
    assert np.isfinite(out["best_return"])
