
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
    setup_logging()

    logger = get_logger("Benchmark")
    logger.info("Starting benchmark...")

    import cProfile
    import pstats

    profiler = cProfile.Profile()
    profiler.enable()

    # Config similar to user
    config = GeneratorConfig(
        max_iterations=100,  # Short run
        indicator_types=["dynamic"],
        mc_iterations=1000,
        use_mc_block_bootstrap=True,  # The slow part
        target_metrics={"profit_factor": 0.5},  # Low target to ensure pass
        population_size=10
    )

    data = generate_synthetic_data(2000)
    generator = IndicatorGenerator(config)

    print("Starting benchmark...")
    start_time = time.time()

    # Mock progress callback to track speed
    def progress(current, total, status):
        print(f"\r{current}/{total} - {status}", end="")

    generator.set_progress_callback(progress)

    try:
        generator.generate(data)
    except KeyboardInterrupt:
        pass

    end_time = time.time()
    profiler.disable()

    with open("profile_stats.txt", "w") as f:
        stats = pstats.Stats(profiler, stream=f).sort_stats("cumtime")
        stats.print_stats(50)

    print(f"\nBenchmark finished in {end_time - start_time:.2f}s")

if __name__ == "__main__":
    benchmark()
