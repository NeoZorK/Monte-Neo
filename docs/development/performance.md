# Performance

Monte-Neo is optimized for high-throughput Monte Carlo simulations.

## Optimizations

1. **C++ Native Extensions**: Hot loops in metrics calculations (trade extraction) are implemented in pure C++ for maximum throughput.
2. **MLX GPU Acceleration**: Massive Monte Carlo scenarios are offloaded to the Apple Silicon GPU via the MLX framework, enabling hundreds of parallel backtests in a single operation.
3. **Multi-Core Parallelism**: Generator search and CPU backtests are distributed across all available CPU cores using a custom `ParallelExecutor`.
4. **Numba JIT**: High-speed Python fallback for environments without a C++ compiler.
5. **Parquet Storage**: Columnar storage for instantaneous data loading.

## Benchmarks

- **Data Load**: 1 year of 1h data in < 0.1s.
- **MC Iteration**: 100k simulations on 5k bars in < 60s (M1 Pro GPU).
- **Metrics**: Native C++ metrics calculation in < 0.5ms.
- **Batch Search**: 1,000 indicator search iterations in < 15s.
