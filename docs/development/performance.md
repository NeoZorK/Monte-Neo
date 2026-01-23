# Performance

Monte-Neo is optimized for high-throughput Monte Carlo simulations.

## Optimizations

1. **Numba JIT**: Hot loops in metrics calculations (drawdown, returns) are compiled using Numba to near-C speeds.
2. **Parallel Processing**: MC iterations are distributed across all available CPU cores using `ProcessPoolExecutor`.
3. **Parquet Storage**: Data is stored using Apache Parquet format, which is 3-5x faster to read/write than CSV and consumes less space.
4. **Vectorized Operations**: Extensive use of NumPy and Pandas vectorization to minimize Python loop overhead.

## Benchmarks

- **Data Load**: 1 year of 1h data in < 0.5s.
- **MC Iteration**: 10,000 simulations on 5,000 bars in < 15s (8-core CPU).
- **Metrics**: Full metrics calculation in < 5ms.
