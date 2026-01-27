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
        p1 = min(fast_period, slow_period)
        p2 = max(fast_period, slow_period)
        
        final_signals = sma_crossover_signals_numba(close, p1, p2)
        return pd.DataFrame({"signal": final_signals}, index=data.index)

    def generate_signals_fast(self, data: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(data, pd.DataFrame):
            close = data["close"].to_numpy()
        else:
            # Assume 1D close prices or OHLC matrix (close is col 3)
            close = data[:, 3] if data.ndim > 1 else data
            
        p1 = min(self._parameters["fast_period"], self._parameters["slow_period"])
        p2 = max(self._parameters["fast_period"], self._parameters["slow_period"])
        return sma_crossover_signals_numba(close, p1, p2)

    def get_formula(self) -> str:
        p1 = min(self._parameters["fast_period"], self._parameters["slow_period"])
        p2 = max(self._parameters["fast_period"], self._parameters["slow_period"])
        return f"SMA({p1}) Cross SMA({p2})"

    def get_min_periods(self) -> int:
        return self._parameters["slow_period"]
