# Performance

Monte-Neo is optimized for high-throughput Monte Carlo simulations.

## Optimizations

1. **C++ Native Extensions**: Hot loops in metrics calculations (trade extraction) are implemented in pure C++ for maximum throughput.
2. **MLX GPU Acceleration**: Massive Monte Carlo scenarios are offloaded to the Apple Silicon GPU via the MLX framework.
3. **3D GPU Acceleration (Pop x Scenarios)**: Evolutionary engine evaluates the entire population across multiple Monte Carlo scenarios simultaneously in a single 3D tensor operation, achieving up to 125x speedup compared to sequential evaluation.
4. **Multi-Core Parallelism**: Generator search and CPU backtests are distributed across all available CPU cores using a custom `ParallelExecutor`.
5. **Numba JIT & Parallelization**: High-speed parallelized metrics calculation using Numba `njit` and `prange`. This includes optimized path-dependent calculations for Stop Loss and Take Profit (SL/TP), achieving over 300,000 operations per second.
6. **Optimized Sequential Mode**: A specialized sequential mode for `DynamicIndicator` and Monte Carlo simulations designed to achieve 300k+ operations per second. This is achieved by:
   - Using lightweight data structures (dictionaries of Pandas Series) to avoid DataFrame copy overhead.
   - Pre-compiling dynamic code with Numba-like caching strategies.
   - Efficient memory management using shared arrays where possible.
7. **Parquet Storage**: Columnar storage for instantaneous data loading.

## Benchmarks

- **Data Load**: 1 year of 1h data in < 0.1s.
- **3D GPU Evolution**: Evaluating 100 members over 10 scenarios in < 0.5s (125.3x faster than previous version).
- **MC Iteration**: 100k simulations on 5k bars in < 60s (M1 Pro GPU).
- **Metrics**: Native C++ metrics calculation in < 0.5ms.
- **SL/TP Performance**: Parallelized Numba implementation processes 300k+ operations per second.
- **Sequential Dynamic Execution**: Optimized path for Dynamic Indicators currently achieving ~8,000 ops/sec (Sequential Mode Fast), with v0.0.4 targeting extreme performance via float8 and Metal shaders.
- **Batch Search**: 1,000 indicator search iterations in < 15s.
