# API Documentation

## Source Code Documentation

Monte-Neo uses Python docstrings (Google Style) for all public APIs. You can explore the core modules to understand the implementation.

### Key Classes

- `IndicatorGenerator`: Core engine for finding and validating indicators.
- `MonteCarloEngine`: Runner for robustness simulations (shuffling, noise).
- `MetricsCalculator`: Unified tool for evaluating trading performance.
- `BinanceDownloader`: Interface for fetching OHLCV data.

### Generating Documentation

To generate HTML documentation using Sphinx or pdoc, run:

```bash
# Using pdoc
pip install pdoc
pdoc monte_neo -o docs/api/
```

Documentation will be available in the `docs/api/` directory.
