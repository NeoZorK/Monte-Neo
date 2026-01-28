"""Evaluator for dynamic indicators.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)

def rsi(data, period=14):
    if isinstance(data, dict):
        close = pd.Series(data['close'])
    else:
        close = data['close'] if hasattr(data, 'close') else data
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def sma(data, period=20):
    if isinstance(data, dict):
        close = pd.Series(data['close'])
    else:
        close = data['close'] if hasattr(data, 'close') else data
    return close.rolling(window=period).mean()

def compile_source(source_code: str) -> Callable[..., Any]:
    """Compile source code into a function."""
    try:
        exec_globals = {
            "np": np,
            "pd": pd,
            "_np": np,
            "_pd": pd,
            "rsi": rsi,
            "sma": sma,
            "__builtins__": __builtins__,
        }

        func_code = (
            f"def _dynamic_calc(data, np, pd):\n    return {source_code}"
        )

        local_scope: dict[str, Any] = {}
        exec(func_code, exec_globals, local_scope)
        return local_scope["_dynamic_calc"]
    except Exception as e:
        logger.debug(f"Failed to compile dynamic indicator: {e}")
        # Fallback to safe source
        safe_source = "data['close']"
        func_code = (
            f"def _dynamic_calc(data, np, pd):\n    return {safe_source}"
        )
        safe_scope: dict[str, Any] = {}
        exec(func_code, exec_globals, safe_scope)
        return safe_scope["_dynamic_calc"]

def evaluate_fast_signals(compiled_code: Callable, data: pd.DataFrame | np.ndarray) -> np.ndarray:
    """Fast version of signal generation."""
    if isinstance(data, pd.DataFrame):
        fast_data = {
            "open": data["open"],
            "high": data["high"],
            "low": data["low"],
            "close": data["close"],
            "volume": data["volume"],
        }
        n_rows = len(data)
    else:
        # If it's a numpy array, check dimensions
        if data.ndim == 1:
            # Only close prices provided (typical for MC scenarios)
            fast_data = {
                "open": pd.Series(data),
                "high": pd.Series(data),
                "low": pd.Series(data),
                "close": pd.Series(data),
                "volume": pd.Series(np.ones_like(data)),
            }
        else:
            # OHLCV provided
            fast_data = {
                "open": pd.Series(data[:, 0]),
                "high": pd.Series(data[:, 1]),
                "low": pd.Series(data[:, 2]),
                "close": pd.Series(data[:, 3]),
                "volume": pd.Series(data[:, 4]),
            }
        n_rows = len(data)

    try:
        vals = compiled_code(fast_data, np, pd)
        
        if isinstance(vals, pd.Series):
            vals = vals.to_numpy()
        
        # Ensure vals is a numpy array and has dimensions
        if not isinstance(vals, np.ndarray):
            vals = np.asarray([vals] * n_rows)
        elif vals.ndim == 0:
            vals = np.full(n_rows, vals)
        elif len(vals) != n_rows:
            # Handle mismatch (e.g. from rolling)
            new_vals = np.full(n_rows, np.nan)
            new_vals[-len(vals):] = vals
            vals = new_vals

        sig_vals = np.zeros(n_rows, dtype=np.float32)
        
        # Standardize signals: >0 is 1, <0 is -1, 0 is 0
        # Use defensive check for NaN
        mask_pos = np.zeros(n_rows, dtype=bool)
        mask_neg = np.zeros(n_rows, dtype=bool)
        
        valid_mask = ~np.isnan(vals)
        mask_pos[valid_mask] = vals[valid_mask] > 0
        mask_neg[valid_mask] = vals[valid_mask] < 0
        
        sig_vals[mask_pos] = 1.0
        sig_vals[mask_neg] = -1.0
        return sig_vals
    except Exception as e:
        logger.debug(f"Error in fast evaluation: {e}")
        return np.zeros(n_rows, dtype=np.float32)
