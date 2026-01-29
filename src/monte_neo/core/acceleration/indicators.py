"""
MLX-accelerated indicators.
"""

from typing import Any

import mlx.core as mx
import numpy as np


class MLXIndicator:
    """Base class for MLX indicators."""
    def compute(self, close: mx.array) -> mx.array:
        """
        Compute indicator.
        Args:
            close: (N, T) matrix of close prices.
        Returns:
            (N, T) matrix of indicator values.
        """
        raise NotImplementedError

class MLXSMA(MLXIndicator):
    def __init__(self, period: int):
        self.period = period
        # Simple average = sum / P
        self.weight = mx.full((1, period, 1), 1.0 / period)

    def compute(self, close: mx.array) -> mx.array:
        """Compute SMA using cumulative sum for O(1) performance and vectorization."""
        if close.dtype != mx.float32 and close.dtype != mx.float16:
            close = close.astype(mx.float32)
        
        # cs[i] = sum(close[0...i])
        cs = mx.cumsum(close, axis=-1)
        
        # SMA(P) at index i: (cs[i] - cs[i-P]) / P
        # For i < P-1, we can use cs[i] / (i+1) or just return 0/nan
        # To match rolling().mean() exactly:
        res = (cs[:, self.period-1:] - mx.concatenate([mx.zeros((cs.shape[0], 1)), cs[:, :-(self.period)]], axis=1)[:, :cs.shape[1]-self.period+1]) / self.period
        
        # Pad with first values to match original length
        # Rolling mean in pandas/numpy usually has NaN for the first P-1 values
        # We'll pad with the first valid SMA value to keep it simple and match previous logic
        pad_vals = mx.repeat(res[:, :1], self.period - 1, axis=1)
        return mx.concatenate([pad_vals, res], axis=1)

class MLXRSI(MLXIndicator):
    """RSI indicator on MLX."""
    def __init__(self, period: int = 14):
        self.period = period

    def compute(self, close: mx.array) -> mx.array:
        # Diff
        diff = close[:, 1:] - close[:, :-1]
        # First diff is 0
        diff = mx.concatenate([mx.zeros((close.shape[0], 1)), diff], axis=1)
        
        gain = mx.where(diff > 0, diff, 0.0)
        loss = mx.where(diff < 0, -diff, 0.0)
        
        # SMA of gains/losses (Simplified version of Wilders)
        # Real RSI uses SMMA/EMA, but SMA is often used as approx or in some variants.
        # Let's use SMA for simplicity in MLX for now.
        sma_gain = MLXSMA(self.period).compute(gain)
        sma_loss = MLXSMA(self.period).compute(loss)
        
        rs = mx.where(sma_loss > 0, sma_gain / sma_loss, 100.0)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

class MLXRollingMax(MLXIndicator):
    def __init__(self, period: int):
        self.period = period

    def compute(self, close: mx.array) -> mx.array:
        # MLX doesn't have a direct rolling_max with window,
        # but we can use a trick with reshape or just use a loop for small windows.
        # For large windows, we might need a more efficient implementation.
        # For now, let's use a simple implementation.
        n, t = close.shape
        res = mx.zeros_like(close)
        for i in range(t):
            start = max(0, i - self.period + 1)
            res[:, i] = mx.max(close[:, start:i+1], axis=1)
        return res

class MLXDynamicStrategy:
    """Fallback strategy that runs Python/Numba logic on MLX data."""
    def __init__(self, indicator: Any):
        self.indicator = indicator

    def generate_signals(self, close: mx.array) -> mx.array:
        # Convert to numpy
        close_np = np.array(close).astype(np.float32)
        
        if close_np.ndim == 1:
            # Single scenario
            signals_np = self.indicator.generate_signals_fast(close_np)
            return mx.array(signals_np)
        
        # Multiple scenarios - run in loop for now
        n_scenarios = close_np.shape[0]
        n_steps = close_np.shape[1]
        all_signals = np.zeros((n_scenarios, n_steps), dtype=np.float32)
        
        for i in range(n_scenarios):
            all_signals[i] = self.indicator.generate_signals_fast(close_np[i])
            
        return mx.array(all_signals)

class MLXCrossStrategy:
    """Simple Crossover Strategy on GPU."""
    
    def __init__(self, indicator: MLXIndicator, mode: str = "greater"):
        self.indicator = indicator
        self.mode = mode
        
    def generate_signals(self, close: mx.array) -> mx.array:
        ind_vals = self.indicator.compute(close)
        if self.mode == "greater":
            state = mx.where(close > ind_vals, 1, -1)
        else:
            state = mx.where(close < ind_vals, 1, -1)
            
        prev_state = mx.concatenate([state[:, :1], state[:, :-1]], axis=1)
        return mx.where(state != prev_state, state, 0)

class MLXSMACrossStrategy:
    """SMA Crossover Strategy on GPU (Fast vs Slow)."""
    
    def __init__(self, fast_period: int, slow_period: int):
        self.fast_sma = MLXSMA(fast_period)
        self.slow_sma = MLXSMA(slow_period)
        
    def generate_signals(self, close: mx.array) -> mx.array:
        fast = self.fast_sma.compute(close)
        slow = self.slow_sma.compute(close)
        state = mx.where(fast > slow, 1, -1)
        prev_state = mx.concatenate([state[:, :1], state[:, :-1]], axis=1)
        return mx.where(state != prev_state, state, 0)
