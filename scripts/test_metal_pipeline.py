
from pathlib import Path

import numpy as np
import pandas as pd

from monte_neo.core.config import GeneratorConfig
from monte_neo.core.generator import IndicatorGenerator
from monte_neo.data.storage import ParquetStorage


def test_pipeline():
    print("Testing Metal Pipeline...")
    
    # Setup data
    data_dir = Path("./data")
    storage = ParquetStorage(data_dir)
    files = storage.list_files()
    
    if not files:
        print("No data found. Creating synthetic data...")
        dates = pd.date_range(start="2020-01-01", periods=1000, freq="1h")
        data = pd.DataFrame({
            "open": np.random.randn(1000).cumsum() + 100,
            "high": np.random.randn(1000).cumsum() + 105,
            "low": np.random.randn(1000).cumsum() + 95,
            "close": np.random.randn(1000).cumsum() + 100,
            "volume": np.random.rand(1000) * 1000
        }, index=dates)
        symbol, timeframe = "TEST", "1h"
    else:
        symbol = files[0]["symbol"]
        timeframe = files[0]["timeframe"]
        data = storage.load(symbol, timeframe)
        print(f"Using data: {symbol} {timeframe}")

    # Config for quick test
    config = GeneratorConfig(
        max_iterations=20, # Reduced
        target_metrics={"profit_factor": 0.5}, # Low target to ensure we find something
        indicator_types=["sma", "rsi", "macd"], # Test all
        mc_iterations=500,
        use_mc_shuffling=True,
        use_mc_noise=False,
        use_mc_sensitivity=False,
        use_mc_walk_forward=False,
        use_mc_block_bootstrap=False,
        use_gpu=True,
        metal_driver="auto"
    )
    
    generator = IndicatorGenerator(config)
    print(f"Starting generation with driver: {config.metal_driver}")
    
    result = generator.generate(data)
    
    print("\n--- Result ---")
    print(f"Success: {result.success}")
    print(f"MC Pass Rate: {result.mc_pass_rate:.1%}")
    print(f"Elapsed Time: {result.elapsed_time:.2f}s")
    
    if "timing_stats" in result.mc_details:
        print("Timing Stats:", result.mc_details["timing_stats"])
    else:
        print("No timing stats found in mc_details")
        
    if result.indicator:
        print(f"Best Indicator: {result.indicator.name}")
        print(f"Formula: {result.indicator.get_formula()}")

if __name__ == "__main__":
    test_pipeline()
