
import time

import numpy as np
import pandas as pd

from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.indicators.technical import MACDIndicator, RSIIndicator, SMAIndicator
from monte_neo.monte_carlo.workers import run_indicator_batch
from monte_neo.utils.parallel import ParallelExecutor


def generate_data(n=1000):
    dates = pd.date_range(start="2023-01-01", periods=n, freq="h")
    df = pd.DataFrame({
        "open": np.random.random(n) * 100,
        "high": np.random.random(n) * 100,
        "low": np.random.random(n) * 100,
        "close": np.random.random(n) * 100,
        "volume": np.random.random(n) * 1000
    }, index=dates)
    return df

def benchmark_indicator(name, indicator_class, data, n_iterations=2000, **kwargs):
    print(f"Benchmarking {name}...")

    # create instances
    indicators = [indicator_class() for _ in range(n_iterations)]
    for ind in indicators:
        if kwargs:
            ind._parameters.update(kwargs)

    # 1. Serial / Sequential Mode (Direct Loop)
    start_time = time.time()
    for ind in indicators:
        ind.generate_signals_fast(data)
    end_time = time.time()

    duration = end_time - start_time
    ops_sec = n_iterations / duration
    print(f"  Sequential Mode: {ops_sec:.2f} ops/sec")

    if ops_sec < 2000:
        print(f"  WARNING: Sequential mode for {name} is below 2000 ops/sec!")

    # 2. Parallel Mode (Executor)
    # We use run_indicator_batch to simulate what GPU engine does
    start_time = time.time()
    with ParallelExecutor(n_workers=4) as executor:
        # Chunking happens in engine, but here we just pass all to one batch to test overhead or split manually
        # Let's split into 4 chunks
        chunk_size = max(1, n_iterations // 4)
        chunks = [indicators[i:i+chunk_size] for i in range(0, n_iterations, chunk_size)]
        tasks = [(chunk, data) for chunk in chunks]

        results = executor.map(run_indicator_batch, tasks)
    end_time = time.time()

    duration = end_time - start_time
    ops_sec_par = n_iterations / duration
    print(f"  Parallel Mode: {ops_sec_par:.2f} ops/sec")

    return ops_sec, ops_sec_par

def main():
    data = generate_data(1000)

    results = {}

    # SMA
    sma_ops, sma_par_ops = benchmark_indicator("SMA", SMAIndicator, data)
    results["SMA"] = sma_ops

    # RSI
    rsi_ops, rsi_par_ops = benchmark_indicator("RSI", RSIIndicator, data)
    results["RSI"] = rsi_ops

    # MACD
    macd_ops, macd_par_ops = benchmark_indicator("MACD", MACDIndicator, data)
    results["MACD"] = macd_ops

    # Dynamic
    # For dynamic, we need to set source code
    # We create a factory/lambda because we need to set param after init
    print("Benchmarking Dynamic...")
    indicators = []
    for _ in range(2000):
        ind = DynamicIndicator()
        ind._parameters["source_code"] = "data['close'] > data['close'].shift(1)"
        indicators.append(ind)

    # Serial Dynamic
    start_time = time.time()
    for ind in indicators:
        ind.generate_signals_fast(data)
    end_time = time.time()
    duration = end_time - start_time
    dyn_ops = 2000 / duration
    print(f"  Sequential Mode (Fast): {dyn_ops:.2f} ops/sec")

    if dyn_ops < 2000:
        print("  WARNING: Sequential mode for Dynamic is below 2000 ops/sec!")

    results["Dynamic"] = dyn_ops

    # Parallel Dynamic
    start_time = time.time()
    with ParallelExecutor(n_workers=4) as executor:
        chunk_size = 2000 // 4
        chunks = [indicators[i:i+chunk_size] for i in range(0, 2000, chunk_size)]
        tasks = [(chunk, data) for chunk in chunks]
        results_par = executor.map(run_indicator_batch, tasks)
    end_time = time.time()

    duration = end_time - start_time
    dyn_par_ops = 2000 / duration
    print(f"  Parallel Mode: {dyn_par_ops:.2f} ops/sec")

    # Final Check
    failures = []
    for name, ops in results.items():
        if ops < 2000:
            failures.append(f"{name} ({ops:.2f} ops/sec)")

    if failures:
        print("\nFAILED: The following indicators did not meet the 2000 ops/sec target in Sequential mode:")
        for f in failures:
            print(f" - {f}")
        exit(1)
    else:
        print("\nSUCCESS: All indicators met performance targets!")

if __name__ == "__main__":
    main()
