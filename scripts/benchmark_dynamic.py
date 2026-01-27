import signal
import sys
import time

import numpy as np
import pandas as pd

from monte_neo.core.config import GeneratorConfig
from monte_neo.core.generator import IndicatorGenerator
from monte_neo.utils.logger import get_logger, setup_logging


def generate_synthetic_data(length=1000):
    dates = pd.date_range(start="2020-01-01", periods=length, freq="1D")
    close = np.random.lognormal(0, 0.02, length).cumprod() * 100
    high = close * (1 + np.random.random(length) * 0.02)
    low = close * (1 - np.random.random(length) * 0.02)
    open_ = close * (1 + np.random.random(length) * 0.01 - 0.005)
    volume = np.random.random(length) * 1000000

    return pd.DataFrame({
        "timestamp": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    }).set_index("timestamp")

def benchmark():
    # Setup signal handler for graceful exit
    def signal_handler(sig, frame):
        print("\n\n[!] Interrupt received. Cleaning up and exiting...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)

    setup_logging()
    logger = get_logger("Benchmark")
    logger.info("Starting benchmark...")

    # Optimization: Reduce iterations for faster verification while keeping it meaningful
    config = GeneratorConfig(
        max_iterations=100,  # Reduced from 1000 for faster check
        indicator_types=["dynamic"],
        mc_iterations=50,    # Reduced from 500
        use_mc_block_bootstrap=True,
        target_metrics={"profit_factor": 0.01},  # Lower target to find candidates faster
        population_size=10,
        early_stopping=True  # Enable early stopping for speed
    )

    data = generate_synthetic_data(1000) # Reduced from 2000
    generator = IndicatorGenerator(config)

    print(f"Starting benchmark with {config.max_iterations} iterations...")
    start_time = time.time()

    # Mock progress callback to track speed
    def progress(current, total, status):
        sys.stdout.write(f"\rProgress: [{current}/{total}] - {status}")
        sys.stdout.flush()

    generator.set_progress_callback(progress)

    try:
        generator.generate(data)
    except KeyboardInterrupt:
        print("\n[!] Benchmark interrupted by user.")
    except Exception as e:
        print(f"\n[!] Error during benchmark: {e}")

    end_time = time.time()
    print(f"\n\nBenchmark finished in {end_time - start_time:.2f}s")

if __name__ == "__main__":
    benchmark()
