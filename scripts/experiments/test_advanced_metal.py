import os
import sys

import numpy as np
import pandas as pd

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

import matplotlib.pyplot as plt

from monte_neo.core.mlx_engine import MLXBacktestEngine
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.utils.visualization import plot_equity_curves, plot_metrics_summary


def test_advanced_metal():
    # 1. Prepare data
    dates = pd.date_range(start="2023-01-01", periods=1000, freq="h")
    np.random.seed(42)
    returns = np.random.normal(0.0001, 0.01, size=1000)
    prices = 100 * (1 + returns).cumprod()
    
    data = pd.DataFrame({
        "open": prices,
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": np.random.randint(100, 1000, size=1000)
    }, index=dates)

    # 2. Test RSI only
    print("\n--- Testing RSI on GPU ---")
    rsi_source = "rsi(data['close'], 14) < 30"
    indicator_rsi = DynamicIndicator()
    indicator_rsi.set_parameters({"source_code": rsi_source})
    
    engine = MLXBacktestEngine()
    results_rsi, timing_rsi = engine.run_full_simulation(data, indicator_rsi, 100)
    print(f"RSI Mean Return: {np.mean([r['metrics']['total_return'] for r in results_rsi]):.2%}")
    print(f"Timing: {timing_rsi}")

    # 3. Test Combined RSI + BB
    print("\n--- Testing Combined RSI & BB on GPU ---")
    # Note: BB pattern in parser expects specific rolling() syntax
    bb_lower = "(data['close'].rolling(20).mean() - 2.0 * data['close'].rolling(20).std())"
    combined_source = f"(data['close'] < {bb_lower}) & (rsi(data['close'], 14) < 40)"
    
    indicator_comb = DynamicIndicator()
    indicator_comb.set_parameters({"source_code": combined_source})
    
    results_comb, timing_comb = engine.run_full_simulation(data, indicator_comb, 100)
    print(f"Combined Mean Return: {np.mean([r['metrics']['total_return'] for r in results_comb]):.2%}")
    print(f"Timing: {timing_comb}")

    # 4. Test Visualization
    print("\n--- Generating Visualization ---")
    plot_metrics_summary(results_comb)
    plt.savefig("advanced_backtest_summary.png")
    print("Summary saved to advanced_backtest_summary.png")
    
    plot_equity_curves(results_comb)
    plt.savefig("advanced_backtest_returns.png")
    print("Returns distribution saved to advanced_backtest_returns.png")

if __name__ == "__main__":
    test_advanced_metal()
