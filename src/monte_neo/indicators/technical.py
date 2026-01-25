"""Technical indicators library.

Common technical indicators for trading.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.indicators.base import BaseIndicator, IndicatorConfig
from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


class TechnicalIndicators:
    """Collection of technical indicator calculations."""

    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average."""
        return data.rolling(window=int(period)).mean()

    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average."""
        return data.ewm(span=int(period), adjust=False).mean()

    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index."""
        period = int(period)
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()

        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(
        data: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """MACD indicator."""
        fast_ema = data.ewm(span=int(fast), adjust=False).mean()
        slow_ema = data.ewm(span=int(slow), adjust=False).mean()
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=int(signal), adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def bollinger_bands(
        data: pd.Series,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Bollinger Bands."""
        middle = data.rolling(period).mean()
        std = data.rolling(period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower

    @staticmethod
    def atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range."""
        period = int(period)
        high = data["high"]
        low = data["low"]
        close = data["close"]

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    @staticmethod
    def stochastic(
        data: pd.DataFrame,
        k_period: int = 14,
        d_period: int = 3,
    ) -> tuple[pd.Series, pd.Series]:
        """Stochastic Oscillator."""
        k_period, d_period = int(k_period), int(d_period)
        low_min = data["low"].rolling(k_period).min()
        high_max = data["high"].rolling(k_period).max()

        k = 100 * ((data["close"] - low_min) / (high_max - low_min))
        d = k.rolling(d_period).mean()
        return k, d


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
        # Optimized: Use numpy for speed
        fast = TechnicalIndicators.sma(data["close"], self._parameters["fast_period"]).to_numpy()
        slow = TechnicalIndicators.sma(data["close"], self._parameters["slow_period"]).to_numpy()

        sig_vals = np.zeros(len(data), dtype=np.float32)
        
        # Crossover signals
        # 1 where fast > slow, -1 where fast < slow
        condition_buy = fast > slow
        condition_sell = fast < slow
        
        sig_vals[condition_buy] = 1.0
        sig_vals[condition_sell] = -1.0
        
        # Only signal on crossover (change from previous)
        # diff = current - previous
        # We want to capture the transition.
        # shift right
        sig_prev = np.roll(sig_vals, 1)
        sig_prev[0] = 0 # Handle first element
        
        diff = sig_vals - sig_prev
        
        final_signals = np.zeros_like(sig_vals)
        final_signals[diff > 0] = 1.0
        final_signals[diff < 0] = -1.0
        
        return pd.DataFrame({"signal": final_signals}, index=data.index)

    def get_min_periods(self) -> int:
        return self._parameters["slow_period"]


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
        # Optimized: Inline calculation, use numpy
        period = self._parameters["period"]
        oversold = self._parameters["oversold"]
        overbought = self._parameters["overbought"]
        
        rsi_series = TechnicalIndicators.rsi(data["close"], period)
        rsi_vals = rsi_series.to_numpy()
        
        sig_vals = np.zeros(len(data), dtype=np.float32)
        
        sig_vals[rsi_vals < oversold] = 1.0
        sig_vals[rsi_vals > overbought] = -1.0
        
        return pd.DataFrame({"signal": sig_vals}, index=data.index)

    def get_min_periods(self) -> int:
        return self._parameters["period"] + 1


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
        # Optimized: Use numpy for speed
        _, _, hist = TechnicalIndicators.macd(
            data["close"],
            self._parameters["fast"],
            self._parameters["slow"],
            self._parameters["signal"],
        )
        hist_vals = hist.to_numpy()

        sig_vals = np.zeros(len(data), dtype=np.float32)
        
        # Histogram crossover
        sig_vals[hist_vals > 0] = 1.0
        sig_vals[hist_vals < 0] = -1.0
        
        # Only signal on crossover
        sig_prev = np.roll(sig_vals, 1)
        sig_prev[0] = 0
        
        diff = sig_vals - sig_prev
        
        final_signals = np.zeros_like(sig_vals)
        final_signals[diff > 0] = 1.0
        final_signals[diff < 0] = -1.0
        
        return pd.DataFrame({"signal": final_signals}, index=data.index)

    def get_min_periods(self) -> int:
        return self._parameters["slow"] + self._parameters["signal"]
