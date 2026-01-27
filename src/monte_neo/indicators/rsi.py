from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.indicators.base import BaseIndicator, IndicatorConfig
from monte_neo.indicators.numba_funcs import rsi_signals_numba
from monte_neo.indicators.technical_lib import TechnicalIndicators


class RSIIndicator(BaseIndicator):
    """RSI indicator with overbought/oversold signals."""

    def __init__(self, config: IndicatorConfig | None = None) -> None:
        super().__init__(config)
        self._parameters.setdefault("period", 14)
        self._parameters.setdefault("overbought", 70)
        self._parameters.setdefault("oversold", 30)

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        result = data.copy()
        result["rsi"] = TechnicalIndicators.rsi(
            data["close"], self._parameters["period"]
        )
        return result

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        # High-performance Numba-based RSI signals
        close = data["close"].to_numpy()
        period = int(round(self._parameters["period"]))
        oversold = float(self._parameters["oversold"])
        overbought = float(self._parameters["overbought"])

        # Minimum period is 2
        period = max(2, period)

        sig_vals = rsi_signals_numba(close, period, oversold, overbought)
        return pd.DataFrame({"signal": sig_vals}, index=data.index)

    def generate_signals_fast(self, data: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(data, pd.DataFrame):
            close = data["close"].to_numpy()
        else:
            close = data[:, 3] if data.ndim > 1 else data

        period = int(round(self._parameters["period"]))
        period = max(2, period)
        oversold = float(self._parameters["oversold"])
        overbought = float(self._parameters["overbought"])

        return rsi_signals_numba(close, period, oversold, overbought)

    def get_formula(self) -> str:
        p = self._parameters["period"]
        ob = self._parameters["overbought"]
        os = self._parameters["oversold"]
        return f"RSI({p}) [Buy < {os}, Sell > {ob}]"

    def get_min_periods(self) -> int:
        return self._parameters["period"] + 1

    def get_metal_params(self) -> list[float] | None:
        """Return parameters for native Metal kernel."""
        # Layout: [type, p1, p2, p3, atr_period, sl_mult, tp_mult, ts_mult]
        # type 1: RSI
        return [
            1.0,  # type
            float(self._parameters.get("period", 14)),
            float(self._parameters.get("overbought", 70)),
            float(self._parameters.get("oversold", 30)),
            14.0, # ATR
            1.5,  # SL
            3.0,  # TP
            2.0   # TS
        ]
