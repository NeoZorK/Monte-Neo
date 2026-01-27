from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.indicators.base import BaseIndicator, IndicatorConfig
from monte_neo.indicators.numba_funcs import sma_crossover_signals_numba
from monte_neo.indicators.technical_lib import TechnicalIndicators


class SMAIndicator(BaseIndicator):
    """SMA Crossover indicator."""

    def __init__(self, config: IndicatorConfig | None = None) -> None:
        super().__init__(config)
        self._parameters.setdefault("fast_period", 10)
        self._parameters.setdefault("slow_period", 20)

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        result = data.copy()
        result["sma_fast"] = TechnicalIndicators.sma(
            data["close"], self._parameters["fast_period"]
        )
        result["sma_slow"] = TechnicalIndicators.sma(
            data["close"], self._parameters["slow_period"]
        )
        return result

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        # High-performance single-pass Numba calculation
        close = data["close"].to_numpy()
        fast_period = self._parameters["fast_period"]
        slow_period = self._parameters["slow_period"]

        # Ensure fast < slow for crossover logic
        # Cast to int for Numba compatibility
        p1 = int(round(min(fast_period, slow_period)))
        p2 = int(round(max(fast_period, slow_period)))

        # Minimum period is 2
        p1 = max(2, p1)
        p2 = max(p1 + 1, p2)

        final_signals = sma_crossover_signals_numba(close, p1, p2)
        return pd.DataFrame({"signal": final_signals}, index=data.index)

    def generate_signals_fast(self, data: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(data, pd.DataFrame):
            close = data["close"].to_numpy()
        else:
            # Assume 1D close prices or OHLC matrix (close is col 3)
            close = data[:, 3] if data.ndim > 1 else data

        p1 = int(round(min(self._parameters["fast_period"], self._parameters["slow_period"])))
        p2 = int(round(max(self._parameters["fast_period"], self._parameters["slow_period"])))

        # Minimum period is 2
        p1 = max(2, p1)
        p2 = max(p1 + 1, p2)

        return sma_crossover_signals_numba(close, p1, p2)

    def get_formula(self) -> str:
        p1 = min(self._parameters["fast_period"], self._parameters["slow_period"])
        p2 = max(self._parameters["fast_period"], self._parameters["slow_period"])
        return f"SMA({p1}) Cross SMA({p2})"

    def get_min_periods(self) -> int:
        return self._parameters["slow_period"]

    def get_metal_params(self) -> list[float] | None:
        """Return parameters for native Metal kernel."""
        # Metal kernel expects: [Fast_Period, Slow_Period, SL_Mult, TP_Mult, TS_Mult]
        return [
            float(self._parameters.get("fast_period", 10)),
            float(self._parameters.get("slow_period", 20)),
            1.5,   # Default SL ATR mult
            3.0,   # Default TP ATR mult
            2.0    # Default TS ATR mult
        ]

    def to_mlx_representation(self):
        try:
            from monte_neo.core.acceleration.indicators import MLXSMACrossStrategy
            fast = int(self._parameters["fast_period"])
            slow = int(self._parameters["slow_period"])
            return MLXSMACrossStrategy(fast, slow)
        except ImportError:
            return None
