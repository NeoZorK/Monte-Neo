"""Dynamic indicator implementation.

Allows for creation of indicators from source code strings.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.indicators.base import BaseIndicator, IndicatorConfig
from monte_neo.indicators.evaluator import compile_source, evaluate_fast_signals
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
            self._compiled_code = compile_source(self.source_code)

    def _reset_to_safe_source(self) -> None:
        if self._parameters.get("source_code") != "data['close']":
            self._parameters["source_code"] = "data['close']"
            self._compiled_code = None

    def _evaluate(self, data: pd.DataFrame | dict[str, Any]) -> Any:
        if self._compiled_code is None:
            self._compile_if_needed()
        
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

    def get_metal_params(self, commission_bps: float = 5.0, slippage_bps: float = 5.0) -> list[float] | None:
        """Return parameters for native Metal kernel if formula is supported."""
        from monte_neo.indicators.metal_parser import parse_metal_params
        return parse_metal_params(self.source_code, commission_bps=commission_bps, slippage_bps=slippage_bps)

    def get_formula(self) -> str:
        """Get the source code string used for calculation."""
        return f"Dynamic: {self.source_code}"

    def to_mlx_representation(self) -> Any | None:
        """Convert to MLX representation for GPU execution.
        
        Tries to map common patterns to native MLX indicators for speed,
        otherwise falls back to MLXDynamicStrategy.
        """
        import re
        from monte_neo.core.acceleration.indicators import (
            MLXSMA, MLXRSI, MLXRollingMax, MLXCrossStrategy, 
            MLXSMACrossStrategy, MLXDynamicStrategy
        )
        
        code = self.source_code.replace(" ", "")
        
        # 1. Price > SMA(P)
        sma_pattern = r"data\['close'\]>data\['close'\]\.rolling\((\d+)\)\.mean\(\)"
        match = re.search(sma_pattern, code)
        if match:
            return MLXCrossStrategy(MLXSMA(int(match.group(1))), mode="greater")
            
        # 2. Price < SMA(P)
        sma_pattern_lt = r"data\['close'\]<data\['close'\]\.rolling\((\d+)\)\.mean\(\)"
        match = re.search(sma_pattern_lt, code)
        if match:
            return MLXCrossStrategy(MLXSMA(int(match.group(1))), mode="less")
            
        # 3. SMA(F) > SMA(S)
        sma_cross_pattern = r"data\['close'\]\.rolling\((\d+)\)\.mean\(\)>data\['close'\]\.rolling\((\d+)\)\.mean\(\)"
        match = re.search(sma_cross_pattern, code)
        if match:
            return MLXSMACrossStrategy(int(match.group(1)), int(match.group(2)))
            
        # 4. RSI < Threshold
        rsi_pattern_lt = r"rsi\(.*?,?(\d+)\)<([\d\.]+)"
        match = re.search(rsi_pattern_lt, code)
        if match:
            # Re-use MLXCrossStrategy but with RSI as indicator
            # Wait, MLXCrossStrategy compares close vs indicator.
            # For RSI < 30, we need a different strategy or a constant indicator.
            # For now, let's just use the fallback for RSI to be safe.
            pass

        # Fallback to general strategy
        return MLXDynamicStrategy(self)

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
        if self._compiled_code is None:
            self._compile_if_needed()
        
        if self._compiled_code is None:
            return np.zeros(len(data), dtype=np.float32)

        return evaluate_fast_signals(self._compiled_code, data)

    def get_min_periods(self) -> int:
        # Difficult to know statically. Default to something safe or 0.
        return 50
