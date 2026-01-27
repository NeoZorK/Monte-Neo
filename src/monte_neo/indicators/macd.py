from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.indicators.base import BaseIndicator, IndicatorConfig
from monte_neo.indicators.numba_funcs import ema_numba
from monte_neo.indicators.technical_lib import TechnicalIndicators


class MACDIndicator(BaseIndicator):
    """MACD crossover indicator."""

    def __init__(self, config: IndicatorConfig | None = None) -> None:
        super().__init__(config)
        self._parameters.setdefault("fast", 12)
        self._parameters.setdefault("slow", 26)
        self._parameters.setdefault("signal", 9)

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        result = data.copy()
        macd, signal, hist = TechnicalIndicators.macd(
            data["close"],
            self._parameters["fast"],
            self._parameters["slow"],
            self._parameters["signal"],
        )
        result["macd"] = macd
        result["macd_signal"] = signal
        result["macd_histogram"] = hist
        return result

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        # High-performance Numba-based MACD signals
        close = data["close"].to_numpy()
        fast_p = self._parameters["fast"]
        slow_p = self._parameters["slow"]
        sig_p = self._parameters["signal"]
        
        fast_ema = ema_numba(close, fast_p)
        slow_ema = ema_numba(close, slow_p)
        macd_line = fast_ema - slow_ema
        signal_line = ema_numba(macd_line, sig_p)
        hist_vals = macd_line - signal_line

        sig_vals = np.zeros(len(data), dtype=np.float32)

        # Histogram crossover
        sig_vals[hist_vals > 0] = 1.0
        sig_vals[hist_vals < 0] = -1.0

        # Only signal on crossover
        sig_prev = np.zeros_like(sig_vals)
        sig_prev[1:] = sig_vals[:-1]

        diff = sig_vals - sig_prev

        final_signals = np.zeros_like(sig_vals)
        final_signals[diff > 0] = 1.0
        final_signals[diff < 0] = -1.0

        return pd.DataFrame({"signal": final_signals}, index=data.index)

    def generate_signals_fast(self, data: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(data, pd.DataFrame):
            close = data["close"].to_numpy()
        else:
            close = data[:, 3] if data.ndim > 1 else data
            
        fast_ema = ema_numba(close, self._parameters["fast"])
        slow_ema = ema_numba(close, self._parameters["slow"])
        macd_line = fast_ema - slow_ema
        signal_line = ema_numba(macd_line, self._parameters["signal"])
        hist_vals = macd_line - signal_line
        
        sig_vals = np.zeros(len(close), dtype=np.float32)
        sig_vals[hist_vals > 0] = 1.0
        sig_vals[hist_vals < 0] = -1.0
        
        sig_prev = np.zeros_like(sig_vals)
        sig_prev[1:] = sig_vals[:-1]
        diff = sig_vals - sig_prev
        
        final_signals = np.zeros_like(sig_vals)
        final_signals[diff > 0] = 1.0
        final_signals[diff < 0] = -1.0
        return final_signals

    def get_formula(self) -> str:
        f = self._parameters["fast"]
        s = self._parameters["slow"]
        sig = self._parameters["signal"]
        return f"MACD({f}, {s}, {sig}) Histogram Cross 0"

    def get_min_periods(self) -> int:
        return self._parameters["slow"] + self._parameters["signal"]
