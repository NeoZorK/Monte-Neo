
import os
import sys

import numpy as np
import pandas as pd

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from monte_neo.core.acceleration.engine import GpuAccelerationEngine


def generate_data(n=1000):
    dates = pd.date_range("2023-01-01", periods=n, freq="h")
    close = np.random.normal(100, 1, n).cumsum()
    # Ensure positive
    close = np.abs(close) + 10
    
    return pd.DataFrame({
        "timestamp": dates,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": np.random.random(n) * 1000
    })

def run():
    print("Generating Data...")
    data = generate_data(1000)
    engine = GpuAccelerationEngine()
    
    # Warmup
    print("Warmup...")
    engine.run_benchmark_simulation(data, 100)
    
    # Run
    n_scenarios = 500000 # 500k scenarios
    print(f"Running Benchmark with {n_scenarios} scenarios...")
    
    res = engine.run_benchmark_simulation(data, n_scenarios)
    
    print(f"Done in {res['elapsed']:.4f}s")
    print(f"Throughput: {res['ops_per_sec']:,.2f} scenarios/sec")

if __name__ == "__main__":
    run()
