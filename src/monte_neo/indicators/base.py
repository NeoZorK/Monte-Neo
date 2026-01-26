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

    def get_id(self) -> str:
        """Get unique identifier for this indicator instance."""
        import json
        params_str = json.dumps(self._parameters, sort_keys=True)
        return f"{self.__class__.__name__}_{params_str}"

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

    def generate_signals_fast(self, data: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Fast version of signal generation returning numpy array.
        
        Default implementation calls generate_signals and extracts the array.
        Subclasses should override this for better performance.
        """
        if isinstance(data, pd.DataFrame):
            sigs = self.generate_signals(data)
            if isinstance(sigs, pd.DataFrame):
                return sigs["signal"].to_numpy(dtype=np.float32)
            return np.asarray(sigs, dtype=np.float32)
        
        # If it's already a numpy array, we might need a dummy DataFrame
        # but this is exactly what we want to avoid.
        # Subclasses MUST override this if they want to support pure numpy paths.
        dummy_df = pd.DataFrame({"close": data[:, 3] if data.ndim > 1 else data})
        return self.generate_signals(dummy_df)["signal"].to_numpy(dtype=np.float32)

    def get_formula(self) -> str:
        """Get the formula or logic of the indicator."""
        return self.name

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
