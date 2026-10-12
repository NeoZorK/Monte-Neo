"""C4: a copy of existing signals is not a new signal; an independent one is."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.alpha.orthogonality import load_existing_scores, signal_orthogonality
from monte_neo.alpha.panel import Panel


def _setup(seed: int = 3, t: int = 600, n: int = 40) -> tuple[Panel, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    a, b = rng.random((t, n)), rng.random((t, n))  # uniform: ranks are linear in values
    ret = 0.01 * rng.standard_normal((t, n)) + 0.004 * (a + b)  # return at t+1 follows both old signals
    close = 100.0 * np.cumprod(1.0 + np.vstack([np.zeros((1, n)), ret[:-1]]), axis=0)
    panel = Panel(pd.bdate_range("2020-01-01", periods=t), [f"S{i:02d}" for i in range(n)], close, a + b)
    return panel, a, b


def test_candidate_that_repeats_existing_scores_warns() -> None:
    panel, a, b = _setup()
    rng = np.random.default_rng(9)
    panel.scores = a + 0.3 * rng.standard_normal(a.shape)
    row = signal_orthogonality(panel, {"a": a, "b": b})
    assert row["id"] == "signal_orthogonality" and row["status"] == "warn", row["summary"]
    assert row["details"]["raw_t"] >= 2 > row["details"]["partial_t"]


def test_independent_candidate_keeps_its_ic() -> None:
    panel, a, b = _setup()
    rng = np.random.default_rng(5)
    t, n = panel.close.shape
    new = rng.standard_normal((t, n))
    ret = 0.01 * rng.standard_normal((t, n)) + 0.004 * (a + b) + 0.01 * new
    panel.close = 100.0 * np.cumprod(1.0 + np.vstack([np.zeros((1, n)), ret[:-1]]), axis=0)
    panel.scores = new
    row = signal_orthogonality(panel, {"a": a, "b": b})
    assert row["status"] == "info", row["summary"]
    assert row["details"]["share_kept"] > 0.8 and row["details"]["partial_t"] > 2


def test_load_existing_scores_aligns_to_panel() -> None:
    panel, a, _ = _setup(t=30)
    long = pd.DataFrame({"timestamp": np.repeat(panel.dates, len(panel.symbols)), "symbol": panel.symbols * len(panel.dates),
                         "mom": a.reshape(-1)})
    got = load_existing_scores(long, panel)
    assert np.allclose(got["mom"], a)
    with pytest.raises(ValueError, match="signal column"):
        load_existing_scores(long[["timestamp", "symbol"]], panel)
    assert signal_orthogonality(panel, long)["status"] in {"skip", "info", "warn"}
