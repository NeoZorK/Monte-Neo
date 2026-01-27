# Performance

Monte-Neo is optimized for high-throughput Monte Carlo simulations.

## Optimizations

1. **C++ Native Extensions**: Hot loops in metrics calculations (trade extraction) are implemented in pure C++ for maximum throughput.
2. **MLX GPU Acceleration**: Massive Monte Carlo scenarios are offloaded to the Apple Silicon GPU via the MLX framework, enabling hundreds of parallel backtests in a single operation.
3. **Multi-Core Parallelism**: Generator search and CPU backtests are distributed across all available CPU cores using a custom `ParallelExecutor`.
4. **Numba JIT & Parallelization**: High-speed parallelized metrics calculation using Numba `njit` and `prange`. This includes optimized path-dependent calculations for Stop Loss and Take Profit (SL/TP), achieving over 300,000 operations per second.
5. **Optimized Sequential Mode**: A specialized sequential mode for `DynamicIndicator` and Monte Carlo simulations designed to achieve 300k+ operations per second. This is achieved by:
   - Using lightweight data structures (dictionaries of Pandas Series) to avoid DataFrame copy overhead.
   - Pre-compiling dynamic code with Numba-like caching strategies.
   - Efficient memory management using shared arrays where possible.
6. **Parquet Storage**: Columnar storage for instantaneous data loading.

## Benchmarks

- **Data Load**: 1 year of 1h data in < 0.1s.
- **MC Iteration**: 100k simulations on 5k bars in < 60s (M1 Pro GPU).
- **Metrics**: Native C++ metrics calculation in < 0.5ms.
- **SL/TP Performance**: Parallelized Numba implementation processes 300k+ operations per second.
- **Sequential Dynamic Execution**: Optimized path for Dynamic Indicators currently achieving ~8,000 ops/sec (Sequential Mode Fast), with v0.0.3 targeting 300,000+ ops/sec.
- **Batch Search**: 1,000 indicator search iterations in < 15s.
