"""Exercise numba modules in a subprocess with NUMBA_DISABLE_JIT=1."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = r"""
import os
os.environ["NUMBA_DISABLE_JIT"] = "1"
import numpy as np
from monte_neo.backtest.core_numba import _stop_hit, run_core_full, run_terminal_return
from monte_neo.indicators.numba_funcs import (
    ema_numba, macd_signals_numba, rsi_numba, rsi_signals_numba,
    sma_crossover_signals_numba, sma_numba,
)
from monte_neo.metrics.numba_funcs import (
    calculate_batch_fast, calculate_batch_multi_price_fast, extract_trades_fast,
)
from monte_neo.oms.accel.match_l2_numba import batch_mid_mark_equity, walk_book_market
from monte_neo.oms.accel.match_numba import batch_terminal_long_flat

rng = np.random.default_rng(0)
n = 64
close = 100 + np.cumsum(rng.normal(0, 0.5, n))
open_ = np.roll(close, 1); open_[0] = close[0]
high = np.maximum(open_, close) + 0.2
low = np.minimum(open_, close) - 0.2
sig = np.zeros(n, dtype=np.int64); sig[10:30] = 1
session = np.ones(n, dtype=np.bool_)
_ = sma_numba(close, 5); _ = ema_numba(close, 5); _ = rsi_numba(close, 14)
_ = sma_crossover_signals_numba(close, 5, 10)
_ = rsi_signals_numba(close, 14, 30.0, 70.0)
_ = macd_signals_numba(close, 8, 16, 5)
_ = _stop_hit(1, 101.0, 99.0, True, True, True, 98.0, 105.0, 100.0, 1.0)
_ = run_terminal_return(
    open_, high, low, close, sig, session, True, False, 0.25,
    5.0, 5.0, 100000.0, 5, 1.0, 2.0, 0.0, 1.0, 1.0, 0.0,
)
_ = run_core_full(
    open_, high, low, close, sig, session, True, False, 0.25,
    5.0, 5.0, 100000.0, 5, 1.0, 2.0, 0.0, 1.0, 1.0, 0.0,
)
prices = close.astype(np.float64)
highs = high.astype(np.float64)
lows = low.astype(np.float64)
sig_m = sig.reshape(1, -1).astype(np.float64)
_ = calculate_batch_fast(prices, highs, lows, sig_m, True, 1.0, 2.0)
_ = calculate_batch_multi_price_fast(
    prices.reshape(1, -1), highs.reshape(1, -1), lows.reshape(1, -1), sig_m, False, 0.0, 0.0
)
_ = extract_trades_fast(prices, highs, lows, sig.astype(np.float64), True, 1.0, 2.0)
_ = batch_terminal_long_flat(open_, close, sig.reshape(1, -1), 5.0, 5.0, 100000.0, 0.25, 5)
bid_px = np.array([99.0, 98.5, 98.0]); ask_px = np.array([101.0, 101.5, 102.0])
bid_sz = np.array([2.0, 2.0, 2.0]); ask_sz = np.array([2.0, 2.0, 2.0])
_ = walk_book_market(1, 1.0, bid_px, bid_sz, ask_px, ask_sz, 5.0, 5.0)
_ = walk_book_market(-1, 1.0, bid_px, bid_sz, ask_px, ask_sz, 5.0, 5.0)
_ = batch_mid_mark_equity(close.astype(np.float64), 1.0, 100000.0)
print("numba_coverage_ok")
"""


def test_numba_modules_under_disable_jit_subprocess():
    env = os.environ.copy()
    env["NUMBA_DISABLE_JIT"] = "1"
    env["PYTHONPATH"] = str(ROOT / "src") + (
        (os.pathsep + env["PYTHONPATH"]) if env.get("PYTHONPATH") else ""
    )
    proc = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        pytest.fail(proc.stdout + "\n" + proc.stderr)
    assert "numba_coverage_ok" in proc.stdout
