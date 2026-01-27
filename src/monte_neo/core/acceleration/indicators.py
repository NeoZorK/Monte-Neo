"""
MLX-accelerated indicators.
"""

import mlx.core as mx


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
        # Create kernel: (Out=1, Kernel=P, In=1)
        # Simple average = sum / P
        self.weight = mx.full((1, period, 1), 1.0 / period)

    def compute(self, close: mx.array) -> mx.array:
        """Compute SMA using 1D convolution."""
        if close.dtype != mx.float32 and close.dtype != mx.float16:
            close = close.astype(mx.float32)
        # Reshape for conv1d: [batch, length, channels]
        # x is [scenarios, time] -> [scenarios, time, 1]
        x = close[..., None]
        out = mx.conv1d(x, self.weight, stride=1, padding=0)
        # Pad beginning with zeros or NaNs to keep same length
        pad_size = self.period - 1
        # In MLX we can't easily pad with NaNs for convolution, 
        # but we can pad with the first value or zeros.
        # Let's pad with first value to avoid signal spikes at start
        padding = mx.repeat(x[:, :1, :], pad_size, axis=1)
        out = mx.concatenate([padding, out], axis=1)
        return out.squeeze(-1)

class MLXCrossStrategy:
    """Simple Crossover Strategy on GPU."""
    
    def __init__(self, indicator: MLXIndicator):
        self.indicator = indicator
        
    def generate_signals(self, close: mx.array) -> mx.array:
        """
        Generate signals: 1 (Buy), -1 (Sell), 0 (Hold).
        Condition: Close > Indicator -> Buy
        """
        ind_vals = self.indicator.compute(close)
        
        # Vectorized logic
        # 1 if close > ind, -1 if close < ind
        # (N, T)
        
        signals = mx.where(close > ind_vals, 1, -1)
        
        # In reality, crossover means transition.
        # But for "state" based (always in market), this works.
        
        return signals

class MLXSMACrossStrategy:
    """SMA Crossover Strategy on GPU (Fast vs Slow)."""
    
    def __init__(self, fast_period: int, slow_period: int):
        self.fast_sma = MLXSMA(fast_period)
        self.slow_sma = MLXSMA(slow_period)
        
    def generate_signals(self, close: mx.array) -> mx.array:
        """
        Generate signals: 1 (Buy), -1 (Sell), 0 (Hold).
        Condition: Fast > Slow -> Buy
        """
        fast = self.fast_sma.compute(close)
        slow = self.slow_sma.compute(close)
        
        # State: 1 if fast > slow, else -1
        state = mx.where(fast > slow, 1, -1)
        
        # Transitions: state[i] - state[i-1]
        # But we want 1 or -1 at the point of change.
        
        # Shift state by 1
        prev_state = mx.concatenate([state[:, :1], state[:, :-1]], axis=1)
        
        # Signal is non-zero only where state changed
        signals = mx.where(state != prev_state, state, 0)
        
        return signals
