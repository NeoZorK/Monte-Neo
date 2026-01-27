"""Verify MetricsCalculator functionality."""

import numpy as np
import pandas as pd
from monte_neo.metrics.calculator import MetricsCalculator

def verify_metrics():
    print("Verifying MetricsCalculator...")
    calc = MetricsCalculator()
    
    # 1. Generate dummy data
    n = 100
    dates = pd.date_range(start="2023-01-01", periods=n, freq="h")
    data = pd.DataFrame({
        "open": np.linspace(100, 200, n),
        "high": np.linspace(101, 201, n),
        "low": np.linspace(99, 199, n),
        "close": np.linspace(100, 200, n), # Uptrend
        "volume": np.ones(n) * 1000
    }, index=dates)
    
    # 2. Generate dummy signals (Buy at 0, Sell at 50)
    signals = np.zeros(n, dtype=np.int32)
    signals[0] = 1
    signals[50] = -1
    signals_df = pd.DataFrame({"signal": signals}, index=dates)
    
    # 3. Test calculate_all
    print("Testing calculate_all...")
    metrics = calc.calculate_all(data, signals_df)
    print(f"Metrics: {metrics}")
    
    assert metrics["trade_count"] == 1
    assert metrics["total_return"] > 0
    assert metrics["profit_factor"] > 1.0 # Should be infinite strictly speaking as no loss
    
    # 4. Test calculate_batch_fast
    print("Testing calculate_batch_fast...")
    prices = data["close"].values
    highs = data["high"].values
    lows = data["low"].values
    
    signal_matrix = np.zeros((2, n), dtype=np.int32)
    signal_matrix[0] = signals
    signal_matrix[1] = signals # Duplicate
    
    batch_results = MetricsCalculator.calculate_batch_fast(
        prices, highs, lows, signal_matrix, False, 0.0, 0.0
    )
    print(f"Batch results shape: {batch_results.shape}")
    print(f"Batch results: {batch_results}")
    
    assert batch_results.shape == (2, 4)
    assert batch_results[0, 3] == 1 # 1 trade
    
    # 5. Test calculate_batch_multi_price_fast
    print("Testing calculate_batch_multi_price_fast...")
    close_matrix = np.zeros((2, n), dtype=np.float64)
    high_matrix = np.zeros((2, n), dtype=np.float64)
    low_matrix = np.zeros((2, n), dtype=np.float64)
    
    close_matrix[0] = prices
    close_matrix[1] = prices
    high_matrix[0] = highs
    high_matrix[1] = highs
    low_matrix[0] = lows
    low_matrix[1] = lows
    
    batch_multi_results = MetricsCalculator.calculate_batch_multi_price_fast(
        close_matrix, high_matrix, low_matrix, signal_matrix, False, 0.0, 0.0
    )
    print(f"Batch multi results shape: {batch_multi_results.shape}")
    print(f"Batch multi results: {batch_multi_results}")
    
    assert batch_multi_results.shape == (2, 4)
    assert batch_multi_results[0, 3] == 1
    
    print("SUCCESS: MetricsCalculator verification passed!")

if __name__ == "__main__":
    verify_metrics()
