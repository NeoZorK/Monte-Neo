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
        # Input: (N, T) -> (N, T, 1)
        x = close.reshape(*close.shape, 1)
        
        # Padding to keep size same?
        # Standard SMA usually returns NaN for first P-1.
        # Conv1d 'valid' reduces size. 'same' keeps size.
        # We can use padding manually.
        # Pad left with NaNs or just zeros?
        # For signal gen, we usually ignore the start.
        
        # Conv1d
        # We need to explicitly pad if we want to match alignment
        # Pad (P-1) on left
        pad_width = [(0,0), (self.period-1, 0), (0,0)]
        # MLX pad syntax might differ, let's stick to valid and then pad result
        
        # Using valid convolution
        out = mx.conv1d(x, self.weight, stride=1, padding=0)
        # out shape: (N, T - P + 1, 1)
        
        # We need to prepend P-1 NaNs/Zeros to match T
        # (N, T, 1)
        N, T = close.shape
        result_len = out.shape[1]
        missing = T - result_len
        
        if missing > 0:
            prefix = mx.zeros((N, missing, 1)) # Use 0 for now
            out = mx.concatenate([prefix, out], axis=1)
            
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
        
        # Vectorized logic
        signals = mx.where(fast > slow, 1, -1)
        return signals
