from __future__ import annotations

import numpy as np
from numba import njit


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
    n = len(data)
    res = np.full(n, np.nan)
    if n <= period:
        return res
    
    # First period calculation (SMA of gains/losses)
    gain_sum = 0.0
    loss_sum = 0.0
    
    for i in range(1, period + 1):
        change = data[i] - data[i-1]
        if change > 0:
            gain_sum += change
        else:
            loss_sum -= change
            
    avg_gain = gain_sum / period
    avg_loss = loss_sum / period
    
    if avg_loss == 0:
        res[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        res[period] = 100.0 - (100.0 / (1.0 + rs))
        
    # Subsequent periods (Wilder's Smoothing)
    for i in range(period + 1, n):
        change = data[i] - data[i-1]
        current_gain = change if change > 0 else 0.0
        current_loss = -change if change < 0 else 0.0
        
        avg_gain = (avg_gain * (period - 1) + current_gain) / period
        avg_loss = (avg_loss * (period - 1) + current_loss) / period
        
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
