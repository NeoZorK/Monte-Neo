import logging
import time

import numpy as np
import pandas as pd

from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.engine import MCConfig, MonteCarloEngine
from monte_neo.utils.parallel import ParallelExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)

def benchmark_mc():
    # Setup data
    n_rows = 730  # Like in user logs
    dates = pd.date_range("2024-01-01", periods=n_rows, freq="D")
    data = pd.DataFrame({
        "open": np.random.uniform(100, 200, n_rows),
        "high": np.random.uniform(100, 200, n_rows),
        "low": np.random.uniform(100, 200, n_rows),
        "close": np.random.uniform(100, 200, n_rows),
        "volume": np.random.uniform(1000, 5000, n_rows),
    }, index=dates)

    # Setup Indicator
    indicator = DynamicIndicator()
    indicator._parameters["source_code"] = "data['close'].rolling(20).mean()"

    # Setup MC
    iterations = 500  # Smaller per run, but we run multiple times
    config = MCConfig(
        iterations=iterations,
        use_shuffling=False,
        use_noise=False,
        use_sensitivity=False,
        use_walk_forward=False,
        use_block_bootstrap=True,
        n_workers=None
    )

    metrics_calc = MetricsCalculator()
    target_metrics = {"profit_factor": 1.0}

    print(f"Generating {iterations} Block Bootstrap scenarios (shared)...")
    # Generate scenarios once to isolate MC engine overhead
    temp_engine = MonteCarloEngine(config)
    scenarios = temp_engine.scenario_builder.generate(data)

    print("\n--- Benchmarking Persistent Executor ---")

    # Initialize persistent executor
    executor = ParallelExecutor()
    executor.__enter__()

    try:
        n_runs = 5
        total_time = 0

        for i in range(n_runs):
            # Pass persistent executor
            engine = MonteCarloEngine(config, executor=executor)

            t0 = time.time()
            engine.run(
                data,
                indicator,
                metrics_calc,
                target_metrics,
                existing_scenarios=scenarios
            )
            elapsed = time.time() - t0
            total_time += elapsed

            speed = iterations / elapsed
            print(f"Run {i+1}: {elapsed:.4f}s | Speed: {speed:.1f} op/s")

        avg_speed = (iterations * n_runs) / total_time
        print(f"\nAverage Speed: {avg_speed:.1f} op/s")

    finally:
        executor.__exit__(None, None, None)

if __name__ == "__main__":
    benchmark_mc()
