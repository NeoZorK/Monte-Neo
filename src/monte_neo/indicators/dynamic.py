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
                func_code = (
                    f"def _dynamic_calc(data, np, pd):\n    return {self.source_code}"
                )
                local_scope: dict[str, Any] = {}
                exec(func_code, {}, local_scope)
                self._compiled_code = local_scope["_dynamic_calc"]
            except Exception as e:
                logger.debug(f"Failed to compile dynamic indicator: {e}")
                self._reset_to_safe_source()
                try:
                    func_code = (
                        f"def _dynamic_calc(data, np, pd):\n    return {self.source_code}"
                    )
                    safe_scope: dict[str, Any] = {}
                    exec(func_code, {}, safe_scope)
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

        indicator_values = self._compiled_code(data, np, pd)

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

    def get_min_periods(self) -> int:
        # Difficult to know statically. Default to something safe or 0.
        return 50
