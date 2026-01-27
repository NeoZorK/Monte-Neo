"""
Tensor operations for MLX-based acceleration.
"""

import mlx.core as mx
import numpy as np
import pandas as pd


def to_tensor(data: pd.DataFrame) -> dict[str, mx.array]:
    """Convert DataFrame to dictionary of MLX arrays."""
    return {
        "open": mx.array(data["open"].values.astype(np.float32)),
        "high": mx.array(data["high"].values.astype(np.float32)),
        "low": mx.array(data["low"].values.astype(np.float32)),
        "close": mx.array(data["close"].values.astype(np.float32)),
        "volume": mx.array(data["volume"].values.astype(np.float32)),
    }

def generate_shuffle_scenarios(
    close: mx.array, n_scenarios: int, seed: int = 42
) -> mx.array:
    """
    Generate shuffled return scenarios on GPU.
    
    Args:
        close: Close prices (T,)
        n_scenarios: Number of scenarios
        
    Returns:
        Matrix of close prices (N, T)
    """
    time_steps = close.shape[0]
    # Calculate returns
    returns = (close[1:] / close[:-1]) - 1.0
    
    # Generate random indices for returns
    # We want to shuffle returns: effectively sampling from returns with replacement or permutation
    # For Monte Carlo "Shuffling", we usually mean Permutation (Sampling without replacement) per scenario?
    # Or Bootstrap (Sampling with replacement)?
    # Usually "Shuffling" implies permutation.
    # But generating N permutations efficiently:
    
    key = mx.random.key(seed)
    # We use uniform sampling to pick indices for now (Bootstrap) as it's faster vectorized
    # Shape (N, T-1)
    indices = mx.random.randint(0, time_steps-1, (n_scenarios, time_steps-1), key=key)
    
    # Gather returns
    shuffled_returns = returns[indices]
    
    # Reconstruct prices
    # P_t = P_0 * prod(1 + r)
    # cumprod in MLX
    
    # (N, T-1) -> (N, T) with P0
    # Add 1 column of zeros for initial return
    # Actually, we just need to cumprod (1+r) and multiply by start price
    
    cum_returns = mx.cumprod(1 + shuffled_returns, axis=1)
    
    # Prepend 1.0 to cum_returns to match shape
    ones = mx.ones((n_scenarios, 1))
    factors = mx.concatenate([ones, cum_returns], axis=1)
    
    # Resulting prices
    start_price = close[0]
    scenarios = start_price * factors
    
    return scenarios

def generate_noise_scenarios(
    close: mx.array, n_scenarios: int, std_dev: float = 0.01, seed: int = 42
) -> mx.array:
    """
    Generate scenarios with Gaussian noise injected into returns.
    """
    time_steps = close.shape[0]
    returns = (close[1:] / close[:-1]) - 1.0
    
    # Repeat returns for N scenarios: (N, T-1)
    base_returns = mx.broadcast_to(returns, (n_scenarios, time_steps-1))
    
    # Generate Noise
    key = mx.random.key(seed)
    noise = mx.random.normal((n_scenarios, time_steps-1), scale=std_dev, key=key)
    
    # Add noise
    noisy_returns = base_returns + noise
    
    # Reconstruct
    cum_returns = mx.cumprod(1 + noisy_returns, axis=1)
    ones = mx.ones((n_scenarios, 1))
    factors = mx.concatenate([ones, cum_returns], axis=1)
    
    start_price = close[0]
    scenarios = start_price * factors
    
    return scenarios
