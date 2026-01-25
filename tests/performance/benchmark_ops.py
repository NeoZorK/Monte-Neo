import time
import pandas as pd
import numpy as np
import os
from monte_neo.core.gpu_engine import MLXBacktestEngine
from monte_neo.indicators.technical import SMAIndicator, RSIIndicator
from monte_neo.utils.parallel import ParallelExecutor
from monte_neo.monte_carlo.workers import init_worker_data
from monte_neo.utils.logger import get_logger

def benchmark():
    # Setup
    data_len = 5000 
    n_indicators = 2000 
    
    print(f"Generating data ({data_len} bars)...")
    dates = pd.date_range(start="2020-01-01", periods=data_len, freq="min")
    df = pd.DataFrame({
        "open": np.random.rand(data_len) * 100,
        "high": np.random.rand(data_len) * 100,
        "low": np.random.rand(data_len) * 100,
        "close": np.random.rand(data_len) * 100,
        "volume": np.random.rand(data_len) * 1000,
    }, index=dates)
    
    # Indicators
    print(f"Creating {n_indicators} indicators...")
    indicators = []
    for i in range(n_indicators):
        if i % 2 == 0:
            ind = SMAIndicator()
            ind.set_parameter("period", 5 + (i % 50))
        else:
            ind = RSIIndicator()
            ind.set_parameter("period", 5 + (i % 25))
        indicators.append(ind)
        
    engine = MLXBacktestEngine()
    
    print(f"Benchmarking {n_indicators} indicators on {data_len} bars...")
    
    # 1. Serial Baseline
    print("Running Serial Baseline...")
    start_serial = time.time()
    # Hack to force serial: pass empty executor or just call manually?
    # gpu_engine falls back to serial if len < 5, but here len is 2000.
    # We can pass n_workers=1 to ParallelExecutor if we create it?
    # Or just use the loop manually.
    for ind in indicators:
        ind.generate_signals(df)
    elapsed_serial = time.time() - start_serial
    ops_sec_serial = n_indicators / elapsed_serial
    print(f"Serial Time: {elapsed_serial:.4f}s, Ops/sec: {ops_sec_serial:.2f}")

    # 2. Parallel with Persistent Pool
    print("Running with GPU MLX + External ParallelExecutor (Persistent Pool)...")
    
    # Create executor outside timing
    executor = ParallelExecutor(
        n_workers=os.cpu_count(),
        initializer=init_worker_data, 
        initargs=(df,)
    )
    
    with executor:
        start = time.time()
        results = engine.backtest_batch(df, indicators, executor=executor, use_shared_data=True)
        elapsed = time.time() - start

    ops_sec = n_indicators / elapsed
    
    print(f"Parallel Time: {elapsed:.4f}s")
    print(f"Parallel Ops/sec: {ops_sec:.2f}")
    
    # 3. Threading
    print("Running with GPU MLX + Threading...")
    executor_threads = ParallelExecutor(
        n_workers=os.cpu_count(),
        use_processes=False,
        initializer=init_worker_data, 
        initargs=(df,)
    )
    with executor_threads:
        start = time.time()
        results = engine.backtest_batch(df, indicators, executor=executor_threads, use_shared_data=True)
        elapsed = time.time() - start
    
    ops_sec_threads = n_indicators / elapsed
    print(f"Threading Time: {elapsed:.4f}s")
    print(f"Threading Ops/sec: {ops_sec_threads:.2f}")

    if ops_sec > 1000:
        print("SUCCESS: Performance > 1000 ops/sec")
    else:
        print("WARNING: Performance < 1000 ops/sec")
    
    return ops_sec

if __name__ == "__main__":
    benchmark()
