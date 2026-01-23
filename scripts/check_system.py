
import pandas as pd
import numpy as np
from monte_neo.core.generator import IndicatorGenerator, GeneratorConfig
from monte_neo.indicators.dynamic import DynamicIndicator
import logging

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO)

def create_dummy_data(days=365):
    dates = pd.date_range("2023-01-01", periods=days, freq="D")
    data = pd.DataFrame(index=dates)
    data["open"] = 100 + np.cumsum(np.random.randn(days))
    data["high"] = data["open"] + np.random.rand(days) * 2
    data["low"] = data["open"] - np.random.rand(days) * 2
    data["close"] = (data["open"] + data["high"] + data["low"]) / 3
    data["volume"] = np.random.rand(days) * 1000
    return data

def check_system():
    print("--- Native System Check: Genetic Algorithms & Dynamic Indicators ---")
    
    data = create_dummy_data()
    print(f"Created dummy data with {len(data)} rows.")
    
    config = GeneratorConfig(
        max_iterations=100,
        population_size=10,
        generations=5,
        indicator_types=["dynamic"],
        mc_iterations=5, # Speed up for check
        target_metrics={"profit_factor": 0.4, "trade_count": 2},
        early_stopping=False
    )
    
    generator = IndicatorGenerator(config)
    
    print("Starting generation...")
    result = generator.generate(data)
    
    print("\n--- Results ---")
    print(f"Success: {result.success}")
    print(f"Iterations tried: {result.iterations_tried}")
    print(f"Candidates found: {result.candidates_found}")
    print(f"Best MC rate: {result.mc_pass_rate:.2%}")
    if result.indicator:
        print(f"Best indicator type: {type(result.indicator).__name__}")
        if isinstance(result.indicator, DynamicIndicator):
            print(f"Best formula: {result.indicator.source_code}")
    print(f"Final metrics: {result.final_metrics}")
    
    if result.indicator is not None:
        print("\nChecking signal generation...")
        signals = result.indicator.generate_signals(data)
        print(f"Signals head:\n{signals.head()}")
        print(f"Signal counts:\n{signals['signal'].value_counts()}")
        
    print("\n--- System Check Complete ---")

if __name__ == "__main__":
    check_system()
