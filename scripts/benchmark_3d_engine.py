
import time
import numpy as np
import pandas as pd
import mlx.core as mx
from monte_neo.core.mlx_engine import MLXBacktestEngine
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.indicators.base import IndicatorConfig

def generate_dummy_data(n_bars=5000):
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n_bars) * 0.1)
    return pd.DataFrame({
        "open": close - 0.05,
        "high": close + 0.1,
        "low": close - 0.1,
        "close": close,
        "volume": np.random.rand(n_bars) * 1000
    })

def benchmark_3d_engine():
    print("🚀 Starting 3D GPU Engine Benchmark...")
    
    n_bars = 5000
    n_pop = 1000
    n_scenarios = 100
    
    data = generate_dummy_data(n_bars)
    engine = MLXBacktestEngine()
    
    # 1. Create a population of indicators
    population = []
    for i in range(n_pop):
        # Simple dynamic formula: close > SMA(period)
        period = 10 + i
        formula = f"data['close'] > data['close'].rolling({period}).mean()"
        ind = DynamicIndicator(IndicatorConfig(name=f"Ind_{i}", parameters={"source_code": formula}))
        population.append(ind)
        
    print(f"📊 Config: Population={n_pop}, Scenarios={n_scenarios}, Bars={n_bars}")
    
    # 2. Benchmark 3D Engine
    start_3d = time.perf_counter()
    results_3d = engine.backtest_population_multi_scenario(
        data, population, n_scenarios=n_scenarios, use_sl_tp=True
    )
    end_3d = time.perf_counter()
    duration_3d = end_3d - start_3d
    
    total_backtests = n_pop * n_scenarios
    speed_3d = total_backtests / duration_3d
    
    print(f"✅ 3D Engine: {duration_3d:.4f}s ({speed_3d:.2f} backtests/sec)")
    
    # 3. Benchmark Sequential (Old way) - just a few to estimate
    print("⏳ Estimating Sequential Speed...")
    n_bench_seq = 5
    start_seq = time.perf_counter()
    for i in range(n_bench_seq):
        # Using 2D batch for single indicator as comparison
        engine.run_full_simulation(data, population[i], n_scenarios=n_scenarios, use_sl_tp=True)
    end_seq = time.perf_counter()
    
    duration_seq_est = (end_seq - start_seq) / n_bench_seq * n_pop
    speed_seq = (n_bench_seq * n_scenarios) / (end_seq - start_seq)
    
    print(f"✅ Sequential (Est): {duration_seq_est:.4f}s ({speed_seq:.2f} backtests/sec)")
    
    improvement = duration_seq_est / duration_3d
    print(f"\n🔥 Improvement: {improvement:.1f}x")
    
    if improvement > 10:
        print("🏆 Benchmark Passed: Significant speedup detected!")
    else:
        print("⚠️ Benchmark Warning: Speedup lower than expected. Check GPU utilization.")

if __name__ == "__main__":
    benchmark_3d_engine()
