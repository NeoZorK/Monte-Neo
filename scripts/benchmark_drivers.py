import time
import numpy as np
try:
    from monte_neo.core.acceleration.cpp_metal.metal_engine import MetalBacktestBridge, Candle, Driver
except ImportError:
    print("❌ Error: metal_engine extension not found. Run compile.sh first.")
    exit(1)

def run_benchmark():
    print("🚀 Starting Metal Driver Benchmark (C++ Extension)...")
    
    # Setup test data
    n_candles = 5000
    n_scenarios = 100000
    
    # Create test candles
    candles = [Candle(100.0, 101.0, 99.0, 100.0, 1000.0) for _ in range(n_candles)]
    params = [1.0, 2.0, 3.0, 4.0, 5.0] # dummy params
    
    drivers = [
        ("Clang C++", Driver.CPP),
        ("Objective-C++", Driver.OBJC),
        ("Apple Swift", Driver.SWIFT)
    ]
    
    results_summary = {}

    for name, driver_enum in drivers:
        print(f"\n--- Testing Driver: {name} ---")
        
        # Initialize bridge
        bridge = MetalBacktestBridge(driver_enum)
        if not bridge.init():
            print(f"❌ Failed to initialize {name}")
            continue
            
        # Warmup (1 iteration)
        print("Warming up...")
        bridge.run_backtest(candles, params, 1000)
        
        # Actual benchmark (3 runs for average)
        n_runs = 3
        durations = []
        sample_res = None
        
        print(f"Running {n_scenarios} scenarios x {n_runs} times...")
        for i in range(n_runs):
            start_time = time.perf_counter()
            results = bridge.run_backtest(candles, params, n_scenarios)
            end_time = time.perf_counter()
            durations.append(end_time - start_time)
            if sample_res is None:
                sample_res = results[0].total_return
        
        avg_duration = sum(durations) / n_runs
        speed = n_scenarios / avg_duration
        
        results_summary[name] = {
            "duration": avg_duration,
            "speed": speed,
            "sample_result": sample_res
        }
        
        print(f"✅ {name} Completed: {avg_duration:.4f}s avg ({speed:.2f} scenarios/sec)")

    print("\n" + "="*70)
    print(f"{'Driver':<20} | {'Avg Time (s)':<12} | {'Scenarios/sec':<15} | {'Consistency'}")
    print("-" * 70)
    
    # Check consistency against C++ driver
    base_result = results_summary.get("Clang C++", {}).get("sample_result", 0)
    
    for name, stats in results_summary.items():
        consistency = "✅ MATCH" if abs(stats["sample_result"] - base_result) < 1e-5 else "❌ MISMATCH"
        print(f"{name:<20} | {stats['duration']:<12.4f} | {stats['speed']:<15.2f} | {consistency}")
    print("="*70)

if __name__ == "__main__":
    run_benchmark()
