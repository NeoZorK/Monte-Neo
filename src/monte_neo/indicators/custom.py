"""Custom indicator builder.

Build custom indicators from combinations of technical indicators.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from monte_neo.indicators.base import BaseIndicator, IndicatorConfig
from monte_neo.indicators.technical import TechnicalIndicators
from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConditionRule:
    """Single condition rule."""

    indicator1: str
    operator: str  # >, <, ==, crosses_above, crosses_below
    indicator2: str | float

    def evaluate(self, data: pd.DataFrame) -> pd.Series:
        """Evaluate the condition."""
        val1 = self._get_value(data, self.indicator1)
        val2 = self._get_value(data, self.indicator2)

        if self.operator == ">":
            return val1 > val2
        elif self.operator == "<":
            return val1 < val2
        elif self.operator == ">=":
            return val1 >= val2
        elif self.operator == "<=":
            return val1 <= val2
        elif self.operator == "==":
            return val1 == val2
        elif self.operator == "crosses_above":
            return (val1 > val2) & (val1.shift(1) <= val2.shift(1))
        elif self.operator == "crosses_below":
            return (val1 < val2) & (val1.shift(1) >= val2.shift(1))
        else:
            raise ValueError(f"Unknown operator: {self.operator}")

    def _get_value(self, data: pd.DataFrame, indicator: str | float) -> pd.Series:
        if isinstance(indicator, (int, float)):
            return pd.Series(indicator, index=data.index)
        return data[indicator]


class CustomIndicatorBuilder:
    """Builder for creating custom indicators."""

    def __init__(self) -> None:
        self._components: list[tuple[str, Callable, dict]] = []
        self._entry_rules: list[ConditionRule] = []
        self._exit_rules: list[ConditionRule] = []
        self._parameters: dict[str, Any] = {}

    def add_sma(self, name: str, period: int) -> CustomIndicatorBuilder:
        """Add SMA component."""
        self._components.append((name, TechnicalIndicators.sma, {"period": period}))
        self._parameters[f"{name}_period"] = period
        return self

    def add_ema(self, name: str, period: int) -> CustomIndicatorBuilder:
        """Add EMA component."""
        self._components.append((name, TechnicalIndicators.ema, {"period": period}))
        self._parameters[f"{name}_period"] = period
        return self

    def add_rsi(self, name: str, period: int = 14) -> CustomIndicatorBuilder:
        """Add RSI component."""
        self._components.append((name, TechnicalIndicators.rsi, {"period": period}))
        self._parameters[f"{name}_period"] = period
        return self

    def add_entry_rule(
        self,
        indicator1: str,
        operator: str,
        indicator2: str | float,
    ) -> CustomIndicatorBuilder:
        """Add entry condition."""
        self._entry_rules.append(ConditionRule(indicator1, operator, indicator2))
        return self

    def add_exit_rule(
        self,
        indicator1: str,
        operator: str,
        indicator2: str | float,
    ) -> CustomIndicatorBuilder:
        """Add exit condition."""
        self._exit_rules.append(ConditionRule(indicator1, operator, indicator2))
        return self

    def build(self, name: str = "CustomIndicator") -> CustomIndicator:
        """Build the custom indicator."""
        config = IndicatorConfig(name=name, parameters=self._parameters)
        indicator = CustomIndicator(config)
        indicator._components = list(self._components)
        indicator._entry_rules = list(self._entry_rules)
        indicator._exit_rules = list(self._exit_rules)
        return indicator


class CustomIndicator(BaseIndicator):
    """Custom indicator built from components."""

    def __init__(self, config: IndicatorConfig | None = None) -> None:
        super().__init__(config)
        self._components: list[tuple[str, Callable, dict]] = []
        self._entry_rules: list[ConditionRule] = []
        self._exit_rules: list[ConditionRule] = []

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        result = data.copy()

        for name, func, params in self._components:
            # Update params from current parameters
            updated_params = {}
            for key, default in params.items():
                param_key = f"{name}_{key}"
                updated_params[key] = self._parameters.get(param_key, default)

            if func in (
                TechnicalIndicators.sma,
                TechnicalIndicators.ema,
                TechnicalIndicators.rsi,
            ):
                result[name] = func(result["close"], **updated_params)

        return result

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        calc = self.calculate(data)
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0

        # Evaluate entry rules (all must be true)
        if self._entry_rules:
            entry_mask = pd.Series(True, index=data.index)
            for rule in self._entry_rules:
                entry_mask &= rule.evaluate(calc)
            signals.loc[entry_mask, "signal"] = 1

        # Evaluate exit rules
        if self._exit_rules:
            exit_mask = pd.Series(True, index=data.index)
            for rule in self._exit_rules:
                exit_mask &= rule.evaluate(calc)
            signals.loc[exit_mask, "signal"] = -1

        return signals

    def get_min_periods(self) -> int:
        max_period = 1
        for _, _, params in self._components:
            period = params.get("period", 1)
            max_period = max(max_period, period)
        return max_period
