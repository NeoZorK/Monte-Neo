"""Deterministic next-bar fill timing tests for monte_neo.backtest."""

from __future__ import annotations

import numpy as np

from monte_neo.backtest import ExecutionModel, run_bar_backtest


def test_signal_fills_on_next_bar_open_not_same_bar() -> None:
    """Signal at bar 5 must fill on bar 6 open (no same-bar lookahead)."""
    n = 20
    open_ = np.full(n, 100.0)
    open_[6] = 110.0  # next-bar open after signal
    high = open_.copy()
    low = open_.copy()
    close = np.full(n, 100.0)
    close[6] = 105.0
    signal = np.zeros(n, dtype=np.int64)
    signal[5] = 1
    model = ExecutionModel(
        fill_policy="next_bar_open",
        side_mode="long_flat",
        size_fraction=1.0,
        commission_bps=0.0,
        slippage_bps=0.0,
        initial_cash=10_000.0,
        warmup_bars=0,
    )
    out = run_bar_backtest(open_, high, low, close, signal, model=model)
    assert out["ok"] is True
    # Entered at 110 open; flattened at last close 100 → loss if filled at 110.
    # If wrongly filled same-bar at 100, return would be ~0 after flatten.
    assert out["n_trades"] >= 2
    assert out["total_return"] < -0.05
