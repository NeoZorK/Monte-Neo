"""Dynamic indicator implementation.

Allows for creation of indicators from source code strings.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.indicators.base import BaseIndicator, IndicatorConfig
from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


class DynamicIndicator(BaseIndicator):
    """Indicator matching the 'Gene' concept where logic is defined by a code string."""

    def __init__(self, config: IndicatorConfig | None = None) -> None:
        super().__init__(config)
        self._parameters.setdefault("source_code", "data['close']")
        self._compiled_code: Callable[..., Any] | None = None

    def __getstate__(self) -> dict[str, Any]:
        """Prepare for pickling by removing compiled code."""
        state = self.__dict__.copy()
        state["_compiled_code"] = None
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore state after unpickling."""
        self.__dict__.update(state)
        self._compiled_code = None

    @property
    def source_code(self) -> str:
        """Get the source code string."""
        return self._parameters["source_code"]

    def _compile_if_needed(self) -> None:
        """Compile the source code if not already compiled."""
        if self._compiled_code is None:
            try:
                # We want to support 'np', 'pd' in the source code
                exec_globals = {
                    "np": np,
                    "pd": pd,
                    "_np": np,
                    "_pd": pd,
                    "__builtins__": __builtins__,
                }

                # Define the function that takes data and the libraries as arguments
                func_code = (
                    f"def _dynamic_calc(data, np, pd):\n    return {self.source_code}"
                )

                local_scope: dict[str, Any] = {}
                exec(func_code, exec_globals, local_scope)
                self._compiled_code = local_scope["_dynamic_calc"]
            except Exception as e:
                logger.debug(f"Failed to compile dynamic indicator: {e}")
                self._reset_to_safe_source()
                try:
                    exec_globals = {
                        "np": np,
                        "pd": pd,
                        "_np": np,
                        "_pd": pd,
                        "__builtins__": __builtins__,
                    }
                    func_code = (
                        f"def _dynamic_calc(data, np, pd):\n    return {self.source_code}"
                    )
                    safe_scope: dict[str, Any] = {}
                    exec(func_code, exec_globals, safe_scope)
                    self._compiled_code = safe_scope["_dynamic_calc"]
                except Exception as safe_error:
                    logger.error(f"Failed to compile safe dynamic indicator: {safe_error}")
                    raise ValueError(
                        f"Invalid indicator source code: {safe_error}"
                    ) from safe_error

    def _reset_to_safe_source(self) -> None:
        if self._parameters.get("source_code") != "data['close']":
            self._parameters["source_code"] = "data['close']"
            self._compiled_code = None

    def _evaluate(self, data: pd.DataFrame | dict[str, Any]) -> Any:
        if self._compiled_code is None:
            self._compile_if_needed()
        
        # Pass numpy and pandas explicitly to the compiled function
        # Using global np and pd for speed
        if self._compiled_code is not None:
            indicator_values = self._compiled_code(data, np, pd)
        else:
            indicator_values = np.nan

        if callable(indicator_values) and not isinstance(
            indicator_values, (pd.Series, pd.DataFrame)
        ):
            try:
                indicator_values = indicator_values()
            except Exception:
                indicator_values = np.nan

        if isinstance(indicator_values, pd.DataFrame):
            indicator_values = (
                indicator_values.iloc[:, 0] if not indicator_values.empty else 0
            )

        return indicator_values

    def _evaluate_with_fallback(self, data: pd.DataFrame | dict[str, Any]) -> Any:
        try:
            return self._evaluate(data)
        except Exception as e:
            logger.debug(f"Runtime error in dynamic indicator: {e}")
            self._reset_to_safe_source()
            try:
                # If data is a dict, we might need to convert it back to DataFrame for fallback
                # but 'data['close']' works for both.
                return self._evaluate(data)
            except Exception as safe_error:
                logger.debug(f"Runtime error in safe dynamic indicator: {safe_error}")
                return np.nan

    def get_metal_params(self) -> list[float] | None:
        """Return parameters for native Metal kernel if formula is supported."""
        import re
        code = self.source_code.replace(" ", "")

        # Layout: [type, p1, p2, p3, atr_period, sl_mult, tp_mult, ts_mult]
        # Default SL/TP/TS params
        common_tail = [14.0, 1.5, 3.0, 2.0]

        # 1. SMA Crossover Pattern: SMA(f) > SMA(s) or Price > SMA(s)
        # Matches: data['close'].rolling(14).mean()>data['close'].rolling(50).mean()
        # or: data['close']>data['close'].rolling(50).mean()
        sma_pattern = r"rolling\((\d+)\)\.mean\(\)"
        matches = re.findall(sma_pattern, code)
        
        if len(matches) == 2:
            if "<" in code:
                # strategy_type 3, sub_type 5 (SMA < SMA)
                return [3.0, 5.0, float(matches[0]), float(matches[1])] + common_tail
            else:
                # SMA(f) > SMA(s)
                return [0.0, float(matches[0]), float(matches[1]), 0.0] + common_tail
        elif len(matches) == 1:
            # Price vs SMA(s)
            if "data['close']>" in code:
                # strategy_type 3, sub_type 0 (Price > SMA)
                return [3.0, 0.0, float(matches[0]), 0.0] + common_tail
            elif "data['close']<" in code:
                # strategy_type 3, sub_type 4 (Price < SMA)
                return [3.0, 4.0, float(matches[0]), 0.0] + common_tail
            elif ">data['close']" in code:
                # strategy_type 0, p1=SMA, p2=1.0 (SMA > Price)
                return [0.0, float(matches[0]), 1.0, 0.0] + common_tail

        # 2. Rolling Max/Min Pattern (Donchian-like)
        # Matches: data['close']>data['high'].rolling(20).max()
        max_pattern = r"data\['high'\]\.rolling\((\d+)\)\.max\(\)"
        max_matches = re.findall(max_pattern, code)
        if max_matches and "data['close']>" in code:
            # strategy_type 3, sub_type 1 (Price > Max)
            return [3.0, 1.0, float(max_matches[0]), 0.0] + common_tail

        min_pattern = r"data\['low'\]\.rolling\((\d+)\)\.min\(\)"
        min_matches = re.findall(min_pattern, code)
        if min_matches and "data['close']<" in code:
            # strategy_type 3, sub_type 2 (Price < Min)
            return [3.0, 2.0, float(min_matches[0]), 0.0] + common_tail

        # 3. Momentum Pattern (Shift/Diff)
        # Matches: data['close']>data['close'].shift(10)
        shift_pattern = r"data\['close'\]\.shift\((\d+)\)"
        shift_matches = re.findall(shift_pattern, code)
        if shift_matches:
            if "data['close']>" in code:
                # strategy_type 3, sub_type 3 (Diff > 0)
                return [3.0, 3.0, float(shift_matches[0]), 0.0] + common_tail
            elif "data['close']<" in code:
                # strategy_type 3, sub_type 6 (Diff < 0)
                return [3.0, 6.0, float(shift_matches[0]), 0.0] + common_tail

        # 2. RSI Pattern: RSI(p) < 30 or RSI(p) > 70
        # Actually RSI is harder to detect in arbitrary dynamic code unless it's explicitly called.
        # But CodeGenerator doesn't produce RSI yet. It produces rolling(p).mean() etc.
        
        # 3. MACD Pattern: MACD is also complex for CodeGenerator.

        # If no simple pattern matched, return None to fallback to MLX/CPU
        return None

    def get_formula(self) -> str:
        """Get the source code string used for calculation."""
        return f"Dynamic: {self.source_code}"

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate indicator values using the generated code.

        Args:
            data: OHLCV DataFrame.

        Returns:
            DataFrame with 'value' column (for now) or dynamic columns.
        """
        result = data.copy()
        indicator_values = self._evaluate_with_fallback(data)

        if isinstance(indicator_values, (pd.Series, np.ndarray)):
            result["dynamic"] = indicator_values
        else:
            result["dynamic"] = indicator_values

        return result

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate signals.

        For dynamic indicators, the 'source_code' might calculate a boolean signal directly,
        or a continuous value.
        """
        vals = self._evaluate_with_fallback(data)

        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0

        vals = pd.to_numeric(vals, errors="coerce")

        if isinstance(vals, pd.Series):
            aligned = vals.reindex(data.index).fillna(0)
        elif isinstance(vals, np.ndarray):
            aligned = pd.Series(vals, index=data.index).fillna(0)
        else:
            aligned = pd.Series([vals] * len(data), index=data.index).fillna(0)

        if aligned.dtype == bool:
            signals.loc[aligned, "signal"] = 1
        else:
            signals.loc[aligned > 0, "signal"] = 1
            signals.loc[aligned < 0, "signal"] = -1

        return signals

    def generate_signals_fast(self, data: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Fast version of signal generation for dynamic indicators."""
        # Use a lightweight data structure if possible
        if isinstance(data, pd.DataFrame):
            # We can pass a dictionary of Series to avoid DataFrame overhead
            # but still support .rolling(), .diff(), etc.
            # This is significantly faster than data.copy() or new DataFrame creation.
            fast_data = {
                "open": data["open"],
                "high": data["high"],
                "low": data["low"],
                "close": data["close"],
                "volume": data["volume"],
            }
            n_rows = len(data)
        else:
            # data is already np.ndarray (OHLCV)
            # We must convert to Series to support pandas operations in source code
            # unless we implement a custom fast rolling library.
            # For now, we create Series from columns.
            fast_data = {
                "open": pd.Series(data[:, 0]),
                "high": pd.Series(data[:, 1]),
                "low": pd.Series(data[:, 2]),
                "close": pd.Series(data[:, 3]),
                "volume": pd.Series(data[:, 4]),
            }
            n_rows = len(data)

        vals = self._evaluate_with_fallback(fast_data)
        
        # Ensure vals is numeric and handle potential conversion issues
        if isinstance(vals, pd.Series):
            vals = vals.values
        
        # If it's still not a numpy array (e.g. single value), broadcast it
        if not isinstance(vals, np.ndarray):
            vals = np.full(n_rows, vals)

        # Standardize signals: >0 is 1, <0 is -1, 0 is 0
        sig_vals = np.zeros(n_rows, dtype=np.float32)
        
        try:
            # Robust check for positive/negative values
            # Handles inf/-inf correctly, and doesn't warn on float32 overflow
            # because we haven't casted to float32 yet.
            sig_vals[np.greater(vals, 0)] = 1.0
            sig_vals[np.less(vals, 0)] = -1.0
        except Exception as e:
            logger.debug(f"Error generating fast signals for dynamic indicator: {e}")
            
        return sig_vals

    def get_min_periods(self) -> int:
        # Difficult to know statically. Default to something safe or 0.
        return 50
