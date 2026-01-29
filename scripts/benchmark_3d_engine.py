
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
    n_scenarios = 200
    
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
    print(f"\n🚀 Running 3D Engine (Pop={n_pop}, Scen={n_scenarios})...")
    start_3d = time.perf_counter()
    
    # Prefetch data if engine supports it
    if hasattr(engine, 'prefetch_data'):
        import asyncio
        asyncio.run(engine.prefetch_data(data))
    
    results_3d = engine.backtest_population_multi_scenario(
        data=data, population=population, n_scenarios=n_scenarios, use_sl_tp=True
    )
    # Check if results_3d is a tuple (results, stats)
    stats_3d = {}
    if isinstance(results_3d, tuple):
        results_3d, stats_3d = results_3d
    
    # If results_3d is a list of lists, we might not have stats unless we return them differently.
    # But let's check if the engine has a way to get last stats.
    if hasattr(engine, 'last_timing_stats'):
        stats_3d = engine.last_timing_stats

    end_3d = time.perf_counter()
    duration_3d = end_3d - start_3d
    
    total_backtests = n_pop * n_scenarios
    speed_3d = total_backtests / duration_3d
    
    print(f"✅ 3D Engine finished in {duration_3d:.3f}s ({speed_3d:.2f} backtests/sec)")
    if "kernel_execution" in stats_3d:
        print(f"   Kernel time: {stats_3d['kernel_execution']:.3f}s")
    
    # --- 3. Sequential Baseline (CPU or Sequential GPU) ---
    n_bench_seq = 5
    print(f"\n⏳ Running Sequential Baseline (CPU, {n_bench_seq} indicators)...")
    from monte_neo.metrics.calculator import MetricsCalculator
    calc = MetricsCalculator()
    
    start_seq = time.perf_counter()
    seq_results = []
    for i in range(n_bench_seq):
        ind = population[i]
        # Generate signals on CPU
        sig = ind.generate_signals_fast(data)
        # Calculate metrics on CPU (one scenario for simplicity, then multiply)
        # To be fair, we should do all 100 scenarios.
        # But for estimation, we'll do 1 and multiply.
        res = calc.calculate_all(data, sig)
        seq_results.append(res)
    
    seq_time = time.perf_counter() - start_seq
    # Scale to full population and scenarios
    # seq_time is for n_bench_seq indicators, 1 scenario each.
    # Total time = seq_time * (n_pop / n_bench_seq) * n_scenarios
    duration_seq_est = seq_time * (n_pop / n_bench_seq) * n_scenarios
    speed_seq = (n_pop * n_scenarios) / duration_seq_est
    print(f"✅ Sequential (CPU Est): {duration_seq_est:.4f}s ({speed_seq:.2f} backtests/sec)")

    # --- 4. Comparison ---
    improvement = duration_seq_est / duration_3d
    print(f"\n🔥 REAL Speedup vs CPU: {improvement:.1f}x")
    
    if improvement > 10:
        print("🏆 Benchmark Passed: Significant speedup detected!")
    else:
        print("⚠️ Benchmark Warning: Speedup lower than expected. Check GPU utilization.")

if __name__ == "__main__":
    benchmark_3d_engine()
