
import time
import pandas as pd
import numpy as np
import sys
import os

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from monte_neo.monte_carlo.engine import MonteCarloEngine
from monte_neo.monte_carlo.types import MCConfig
from monte_neo.indicators.base import BaseIndicator, IndicatorConfig
from monte_neo.metrics.calculator import MetricsCalculator

# Simple Indicator
class BenchmarkIndicator(BaseIndicator):
    def __init__(self):
        super().__init__(IndicatorConfig(name="BenchmarkSMA", parameters={"period": 10}))
        self.period = 10

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        close = df["close"].values
        sma = np.zeros_like(close)
        kernel = np.ones(self.period) / self.period
        sma[self.period-1:] = np.convolve(close, kernel, mode='valid')
        df["sma"] = sma
        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = self.calculate(data)
        df["signal"] = 0
        close = df["close"].values
        sma = df["sma"].values
        df.loc[self.period:, "signal"] = np.where(close[self.period:] > sma[self.period:], 1, -1)
        return df

    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.generate_signals(data)

def generate_data(n=1000):
    dates = pd.date_range("2023-01-01", periods=n, freq="h")
    close = np.random.normal(100, 1, n).cumsum()
    high = close + np.random.random(n)
    low = close - np.random.random(n)
    open_ = close + np.random.normal(0, 0.5, n)
    volume = np.random.random(n) * 1000
    return pd.DataFrame({
        "timestamp": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    })

def run_benchmark():
    data = generate_data(1000)
    indicator = BenchmarkIndicator()
    metrics_calc = MetricsCalculator()
    
    # Configure MC
    n_scenarios = 1000
    config = MCConfig(
        use_shuffling=True,
        iterations=n_scenarios,
        random_seed=42,
        use_sl_tp=False # Start without SL/TP for max throughput test
    )
    
    engine = MonteCarloEngine(config=config)
    
    print(f"Running Benchmark with {n_scenarios} scenarios...")
    print(f"Data length: {len(data)}")
    
    start = time.time()
    result = engine.run(data, indicator, metrics_calc, {"profit_factor": 1.0})
    elapsed = time.time() - start
    
    ops_per_sec = n_scenarios / elapsed
    print(f"Completed in {elapsed:.4f}s")
    print(f"Throughput: {ops_per_sec:.2f} scenarios/sec")
    
    return ops_per_sec

if __name__ == "__main__":
    run_benchmark()
