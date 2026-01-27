"""Dynamic indicator implementation.

Allows for creation of indicators from source code strings.
"""

from __future__ import annotations

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
        self._compiled_code = None

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
                # Import inside to make them available in the scope of exec
                import numpy as _np
                import pandas as _pd

                # We want to support 'np', 'pd', '_np', '_pd' in the source code
                # The easiest way is to provide them in the globals of the exec
                exec_globals = {
                    "np": _np,
                    "pd": _pd,
                    "_np": _np,
                    "_pd": _pd,
                    "__builtins__": __builtins__,
                }

                # Define the function that takes data and the libraries as arguments
                # even though they are also in globals, for extra safety and clarity
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
                    import numpy as _np
                    import pandas as _pd
                    exec_globals = {
                        "np": _np,
                        "pd": _pd,
                        "_np": _np,
                        "_pd": _pd,
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

    def _evaluate(self, data: pd.DataFrame) -> Any:
        self._compile_if_needed()
        assert self._compiled_code is not None

        # Pass numpy and pandas explicitly to the compiled function
        import numpy as _np
        import pandas as _pd
        indicator_values = self._compiled_code(data, _np, _pd)

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

    def _evaluate_with_fallback(self, data: pd.DataFrame) -> Any:
        try:
            return self._evaluate(data)
        except Exception as e:
            logger.debug(f"Runtime error in dynamic indicator: {e}")
            self._reset_to_safe_source()
            try:
                return self._evaluate(data)
            except Exception as safe_error:
                logger.debug(f"Runtime error in safe dynamic indicator: {safe_error}")
                return np.nan

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
        if not isinstance(data, pd.DataFrame):
            # Dynamic indicator currently requires DataFrame for its evaluation logic
            # (e.g. data['close'] in source_code). Convert back if needed.
            # This is a bit slow but better than the default implementation.
            df = pd.DataFrame(data, columns=["open", "high", "low", "close", "volume"])
        else:
            df = data

        vals = self._evaluate_with_fallback(df)
        
        # Fast conversion to float32 array
        if isinstance(vals, (pd.Series, np.ndarray)):
            vals_arr = np.asarray(vals, dtype=np.float32)
        else:
            vals_arr = np.full(len(df), vals, dtype=np.float32)
            
        # Standardize signals: >0 is 1, <0 is -1, 0 is 0
        sig_vals = np.zeros_like(vals_arr)
        sig_vals[vals_arr > 0] = 1.0
        sig_vals[vals_arr < 0] = -1.0
        
        return sig_vals

    def get_min_periods(self) -> int:
        # Difficult to know statically. Default to something safe or 0.
        return 50
