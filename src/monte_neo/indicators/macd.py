from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.indicators.base import BaseIndicator, IndicatorConfig
from monte_neo.indicators.numba_funcs import macd_signals_numba
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
        fast_p = int(round(self._parameters["fast"]))
        slow_p = int(round(self._parameters["slow"]))
        sig_p = int(round(self._parameters["signal"]))

        # Minimum period is 2
        fast_p = max(2, fast_p)
        slow_p = max(fast_p + 1, slow_p)
        sig_p = max(2, sig_p)

        sig_vals = macd_signals_numba(close, fast_p, slow_p, sig_p)
        return pd.DataFrame({"signal": sig_vals}, index=data.index)

    def generate_signals_fast(self, data: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(data, pd.DataFrame):
            close = data["close"].to_numpy()
        else:
            close = data[:, 3] if data.ndim > 1 else data

        fast_p = int(round(self._parameters["fast"]))
        slow_p = int(round(self._parameters["slow"]))
        sig_p = int(round(self._parameters["signal"]))

        # Minimum period is 2
        fast_p = max(2, fast_p)
        slow_p = max(fast_p + 1, slow_p)
        sig_p = max(2, sig_p)

        return macd_signals_numba(close, fast_p, slow_p, sig_p)

    def get_formula(self) -> str:
        f = self._parameters["fast"]
        s = self._parameters["slow"]
        sig = self._parameters["signal"]
        return f"MACD({f}, {s}, {sig}) Histogram Cross 0"

    def get_min_periods(self) -> int:
        return self._parameters["slow"] + self._parameters["signal"]

    def get_metal_params(self, commission_bps: float = 0.0, slippage_bps: float = 0.0) -> list[float] | None:
        """Return parameters for native Metal kernel."""
        # Layout: [type, p1, p2, p3, atr_period, sl_mult, tp_mult, ts_mult, commission, slippage]
        # type 2: MACD
        return [
            2.0,  # type
            float(self._parameters.get("fast", 12)),
            float(self._parameters.get("slow", 26)),
            float(self._parameters.get("signal", 9)),
            14.0, # ATR
            1.5,  # SL
            3.0,  # TP
            2.0,  # TS
            commission_bps,
            slippage_bps
        ]
