"""
Tensor operations for MLX-based acceleration.
"""

import mlx.core as mx
import numpy as np
import pandas as pd


class TensorOps:
    """Collection of MLX-based tensor operations."""

    @staticmethod
    def to_tensor(data: pd.DataFrame) -> dict[str, mx.array]:
        """Convert DataFrame to dictionary of MLX arrays."""
        return {
            "open": mx.array(data["open"].values.astype(np.float32)),
            "high": mx.array(data["high"].values.astype(np.float32)),
            "low": mx.array(data["low"].values.astype(np.float32)),
            "close": mx.array(data["close"].values.astype(np.float32)),
            "volume": mx.array(data["volume"].values.astype(np.float32)),
        }

    @staticmethod
    def moving_average(data: mx.array, period: int) -> mx.array:
        """
        Calculate Simple Moving Average on MLX.
        Uses a sliding window approach with convolution.
        """
        if period <= 1:
            return data
            
        # MLX conv1d default: input (N, L, C), weight (O, K, I)
        # N: batch, L: length, C: channels
        # O: out_channels, K: kernel_width, I: in_channels
        
        is_1d = len(data.shape) == 1
        if is_1d:
            # (1, T, 1)
            x = data[None, :, None]
        else:
            # (N, T, 1)
            x = data[:, :, None]
            
        # Pad to keep same length
        # Padding for 'same' with causal behavior (pad left)
        # padding is list of (before, after) for each dimension
        padding = [(0, 0), (period - 1, 0), (0, 0)]
        x_padded = mx.pad(x, padding, constant_values=x[:, 0:1, :])
        
        # Kernel: (1, period, 1)
        kernel = mx.ones((1, period, 1)) / period
        
        out = mx.conv1d(x_padded, kernel)
        
        if is_1d:
            return out.reshape(-1)
        else:
            return out.reshape(data.shape)

    @staticmethod
    def generate_shuffle_scenarios(
        close: mx.array, n_scenarios: int, seed: int = 42
    ) -> mx.array:
        """
        Generate shuffled return scenarios on GPU.
        """
        time_steps = close.shape[0]
        returns = (close[1:] / close[:-1]) - 1.0
        
        key = mx.random.key(seed)
        indices = mx.random.randint(0, time_steps-1, (n_scenarios, time_steps-1), key=key)
        
        shuffled_returns = returns[indices]
        cum_returns = mx.cumprod(1 + shuffled_returns, axis=1)
        
        ones = mx.ones((n_scenarios, 1))
        factors = mx.concatenate([ones, cum_returns], axis=1)
        
        start_price = close[0]
        scenarios = start_price * factors
        
        return scenarios

    @staticmethod
    def generate_noise_scenarios(
        close: mx.array, n_scenarios: int, std_dev: float = 0.01, seed: int = 42
    ) -> mx.array:
        """
        Generate scenarios with Gaussian noise injected into returns.
        """
        time_steps = close.shape[0]
        returns = (close[1:] / close[:-1]) - 1.0
        
        base_returns = mx.broadcast_to(returns, (n_scenarios, time_steps-1))
        
        key = mx.random.key(seed)
        noise = mx.random.normal((n_scenarios, time_steps-1), scale=std_dev, key=key)
        
        noisy_returns = base_returns + noise
        
        cum_returns = mx.cumprod(1 + noisy_returns, axis=1)
        ones = mx.ones((n_scenarios, 1))
        factors = mx.concatenate([ones, cum_returns], axis=1)
        
        start_price = close[0]
        scenarios = start_price * factors
        
        return scenarios


# Maintain backward compatibility for functional imports if needed
to_tensor = TensorOps.to_tensor
generate_shuffle_scenarios = TensorOps.generate_shuffle_scenarios
generate_noise_scenarios = TensorOps.generate_noise_scenarios
