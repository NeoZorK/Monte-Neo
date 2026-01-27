"""Evaluator for dynamic indicators.
"""

from __future__ import annotations
from typing import Any, Callable
import numpy as np
import pandas as pd
from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)

def compile_source(source_code: str) -> Callable[..., Any]:
    """Compile source code into a function."""
    try:
        exec_globals = {
            "np": np,
            "pd": pd,
            "_np": np,
            "_pd": pd,
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
            vals = vals.values
        
        if not isinstance(vals, np.ndarray):
            vals = np.full(n_rows, vals)

        sig_vals = np.zeros(n_rows, dtype=np.float32)
        
        # Standardize signals: >0 is 1, <0 is -1, 0 is 0
        sig_vals[np.greater(vals, 0)] = 1.0
        sig_vals[np.less(vals, 0)] = -1.0
        return sig_vals
    except Exception as e:
        logger.debug(f"Error in fast evaluation: {e}")
        return np.zeros(n_rows, dtype=np.float32)
