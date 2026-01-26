"""Technical indicators library.

Common technical indicators for trading.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

from monte_neo.indicators.base import BaseIndicator, IndicatorConfig
from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


@njit
def sma_numba(data: np.ndarray, period: int) -> np.ndarray:
    """Fast SMA calculation."""
    res = np.full(data.shape, np.nan)
    if len(data) < period:
        return res
    
    current_sum = 0.0
    for i in range(period):
        current_sum += data[i]
    
    res[period - 1] = current_sum / period
    
    for i in range(period, len(data)):
        current_sum = current_sum - data[i - period] + data[i]
        res[i] = current_sum / period
        
    return res


@njit
def ema_numba(data: np.ndarray, period: int) -> np.ndarray:
    """Fast EMA calculation."""
    res = np.full(data.shape, np.nan)
    if len(data) == 0:
        return res
    
    alpha = 2.0 / (period + 1)
    res[0] = data[0]
    
    for i in range(1, len(data)):
        res[i] = (data[i] - res[i - 1]) * alpha + res[i - 1]
        
    return res


@njit
def rsi_numba(data: np.ndarray, period: int) -> np.ndarray:
    """Fast RSI calculation."""
    res = np.full(data.shape, np.nan)
    if len(data) <= period:
        return res
    
    deltas = np.diff(data)
    gains = np.zeros(len(deltas))
    losses = np.zeros(len(deltas))
    
    for i in range(len(deltas)):
        if deltas[i] > 0:
            gains[i] = deltas[i]
        else:
            losses[i] = -deltas[i]
            
    avg_gain = 0.0
    avg_loss = 0.0
    
    for i in range(period):
        avg_gain += gains[i]
        avg_loss += losses[i]
        
    avg_gain /= period
    avg_loss /= period
    
    if avg_loss == 0:
        res[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        res[period] = 100.0 - (100.0 / (1.0 + rs))
        
    for i in range(period + 1, len(data)):
        # Wilder's smoothing
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        
        if avg_loss == 0:
            res[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            res[i] = 100.0 - (100.0 / (1.0 + rs))
            
    return res


@njit
def sma_crossover_signals_numba(data: np.ndarray, fast_period: int, slow_period: int) -> np.ndarray:
    """Full SMA crossover signal generation in a single Numba pass."""
    n = len(data)
    res = np.zeros(n, dtype=np.float32)
    if n < slow_period or fast_period >= slow_period:
        return res
    
    sum_fast = 0.0
    sum_slow = 0.0
    
    # Initial sums
    for i in range(fast_period):
        sum_fast += data[i]
    for i in range(slow_period):
        sum_slow += data[i]
        
    # Initial state
    sma_fast = sum_fast / fast_period
    sma_slow = sum_slow / slow_period
    prev_state = 1 if sma_fast > sma_slow else -1
    
    for i in range(slow_period, n):
        sum_fast = sum_fast - data[i - fast_period] + data[i]
        sum_slow = sum_slow - data[i - slow_period] + data[i]
        
        sma_fast = sum_fast / fast_period
        sma_slow = sum_slow / slow_period
        
        current_state = 1 if sma_fast > sma_slow else -1
        
        if current_state != prev_state:
            res[i] = float(current_state)
            prev_state = current_state
            
    return res


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
        # High-performance single-pass Numba calculation
        close = data["close"].to_numpy()
        fast_period = self._parameters["fast_period"]
        slow_period = self._parameters["slow_period"]
        
        # Ensure fast < slow for crossover logic
        p1 = min(fast_period, slow_period)
        p2 = max(fast_period, slow_period)
        
        final_signals = sma_crossover_signals_numba(close, p1, p2)
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
        # High-performance Numba-based RSI signals
        close = data["close"].to_numpy()
        period = self._parameters["period"]
        oversold = self._parameters["oversold"]
        overbought = self._parameters["overbought"]

        rsi_vals = rsi_numba(close, period)

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

    def get_min_periods(self) -> int:
        return self._parameters["slow"] + self._parameters["signal"]
