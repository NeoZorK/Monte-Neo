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

    @property
    def source_code(self) -> str:
        """Get the source code string."""
        return self._parameters["source_code"]

    def _compile_if_needed(self) -> None:
        """Compile the source code if not already compiled."""
        if self._compiled_code is None:
            try:
                # We compile it as an expression that returns a value given 'data', 'np', 'pd'
                # For safety, we wrap it in a function definition
                func_code = (
                    f"def _dynamic_calc(data, np, pd):\n"
                    f"    return {self.source_code}"
                )
                local_scope: dict[str, Any] = {}
                exec(func_code, {}, local_scope)
                self._compiled_code = local_scope["_dynamic_calc"]
            except Exception as e:
                logger.error(f"Failed to compile dynamic indicator: {e}")
                raise ValueError(f"Invalid indicator source code: {e}") from e

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate indicator values using the generated code.

        Args:
            data: OHLCV DataFrame.

        Returns:
            DataFrame with 'value' column (for now) or dynamic columns.
        """
        self._compile_if_needed()
        assert self._compiled_code is not None

        result = data.copy()
        try:
            # Execute the compiled function
            # We provide a limited scope
            indicator_values = self._compiled_code(data, np, pd)
            
            # If it's a callable (like a method accidentally returned without parentheses)
            if callable(indicator_values) and not isinstance(indicator_values, (pd.Series, pd.DataFrame)):
                try:
                    indicator_values = indicator_values()
                except:
                    pass

            # Ensure it returns a Series or DataFrame
            if isinstance(indicator_values, (pd.Series, np.ndarray)):
                result["dynamic"] = indicator_values
            elif isinstance(indicator_values, pd.DataFrame):
                result["dynamic"] = indicator_values.iloc[:, 0] if not indicator_values.empty else 0
            else:
                # If scalar, broadcast to series
                result["dynamic"] = indicator_values

        except Exception as e:
            logger.error(f"Runtime error in dynamic indicator: {e}")
            result["dynamic"] = np.nan

        return result

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate signals.

        For dynamic indicators, the 'source_code' might calculate a boolean signal directly,
        or a continuous value.
        
        If the value is boolean:
            True -> 1 (Buy)
            False -> -1 (Sell) (or 0?)
            
        If numerical, we might need a threshold. For now, let's assume the
        generator produces a signal-like value or we use a wrapper.
        
        Strategy:
        If the result is boolean: True=Buy(1), False=Hold(0).
        (This is simplistic, usually we want Buy/Sell/Hold).
        
        Let's assume the generated code RETURNS a signal directly (-1, 0, 1) usually.
        Or, we can have a conventions.
        
        For this implementation, let's assume the source_code *returns a Series of signals* 
        OR a Series of values that are interpreted as >0 buy, <0 sell.
        """
        calc = self.calculate(data)
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        
        vals = calc["dynamic"]
        
        # If boolean
        if vals.dtype == bool:
             signals.loc[vals, "signal"] = 1
             # If strictly boolean, we might not have Sell signals.
             # Maybe not ideal.
        else:
            # If numeric, >0 is Buy, <0 is Sell
            signals.loc[vals > 0, "signal"] = 1
            signals.loc[vals < 0, "signal"] = -1
            
        return signals

    def get_min_periods(self) -> int:
        # Difficult to know statically. Default to something safe or 0.
        return 50
