"""One entry point for the verifier's backtests.

Sign positions (int64 ``{-1, 0, 1}``) run on the discrete engine, so certificates
of sign strategies keep their exact numbers. Weights (float64) and multi-instrument
matrices run on the target-weight engine, which equals the discrete engine on unit
signals.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.backtest.bar_engine import run_bar_equity
from monte_neo.backtest.model import ExecutionModel
from monte_neo.backtest.weight_engine import run_weight_backtest


def is_weights(positions: np.ndarray) -> bool:
    """True for weight positions (float) or a multi-instrument matrix."""
    arr = np.asarray(positions)
    return arr.dtype.kind == "f" or arr.ndim == 2


def simulate(ohlc: dict[str, np.ndarray], positions: np.ndarray, model: ExecutionModel) -> dict[str, Any]:
    """Backtest ``positions`` on ``ohlc``; returns equity, total_return, max_drawdown, n_trades, n_closed_trades."""
    if is_weights(positions):
        return run_weight_backtest(
            ohlc["open"], ohlc["close"], np.asarray(positions, dtype=np.float64), model=model, high=ohlc["high"], low=ohlc["low"]
        )
    return run_bar_equity(ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], positions, model=model)


def total_return(ohlc: dict[str, np.ndarray], positions: np.ndarray, model: ExecutionModel) -> float:
    """Net total return of ``positions``."""
    return float(simulate(ohlc, positions, model)["total_return"])


__all__ = ["is_weights", "simulate", "total_return"]
