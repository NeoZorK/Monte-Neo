"""Base indicator class.

Abstract base class for all trading indicators.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class IndicatorConfig:
    """Indicator configuration."""
    
    name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    entry_conditions: list[str] = field(default_factory=list)
    exit_conditions: list[str] = field(default_factory=list)


class BaseIndicator(ABC):
    """Abstract base class for trading indicators."""

    def __init__(self, config: IndicatorConfig | None = None) -> None:
        """Initialize indicator.

        Args:
            config: Indicator configuration.
        """
        self.config = config or IndicatorConfig(name=self.__class__.__name__)
        self._parameters: dict[str, Any] = dict(self.config.parameters)

    @property
    def name(self) -> str:
        """Get indicator name."""
        return self.config.name

    def get_parameters(self) -> dict[str, Any]:
        """Get all parameters.

        Returns:
            Dictionary of parameter names to values.
        """
        return dict(self._parameters)

    def set_parameter(self, name: str, value: Any) -> None:
        """Set a parameter value.

        Args:
            name: Parameter name.
            value: Parameter value.
        """
        self._parameters[name] = value
        logger.debug(f"Set {name}={value}")

    def set_parameters(self, params: dict[str, Any]) -> None:
        """Set multiple parameters.

        Args:
            params: Dictionary of parameters.
        """
        for name, value in params.items():
            self.set_parameter(name, value)

    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate indicator values.

        Args:
            data: OHLCV DataFrame.

        Returns:
            DataFrame with indicator values.
        """
        pass

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals.

        Args:
            data: OHLCV DataFrame.

        Returns:
            DataFrame with 'signal' column (1=buy, -1=sell, 0=hold).
        """
        pass

    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate input data.

        Args:
            data: OHLCV DataFrame.

        Returns:
            True if data is valid.
        """
        required_cols = ["open", "high", "low", "close", "volume"]
        
        for col in required_cols:
            if col not in data.columns:
                logger.warning(f"Missing column: {col}")
                return False
        
        if len(data) < 10:
            logger.warning("Insufficient data points")
            return False
        
        return True

    def get_min_periods(self) -> int:
        """Get minimum periods required for calculation.

        Returns:
            Minimum number of periods.
        """
        return 1

    def to_dict(self) -> dict:
        """Convert indicator to dictionary.

        Returns:
            Serializable dictionary.
        """
        return {
            "name": self.name,
            "class": self.__class__.__name__,
            "parameters": self.get_parameters(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> BaseIndicator:
        """Create indicator from dictionary.

        Args:
            data: Dictionary representation.

        Returns:
            Indicator instance.
        """
        config = IndicatorConfig(
            name=data.get("name", cls.__name__),
            parameters=data.get("parameters", {}),
        )
        instance = cls(config)
        instance.set_parameters(data.get("parameters", {}))
        return instance
