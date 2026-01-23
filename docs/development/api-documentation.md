# API Documentation

## Why is this document minimal?

Currently, this document serves as a high-level guide to the core API components. The absolute source of truth is the **source code itself**, which is fully documented using Google Style docstrings.

As the project matures into a stable v1.0, this document will be expanded with detailed tutorials and signature explanations.

### Key Classes

- `IndicatorGenerator`: Core engine for finding and validating indicators.
- `MonteCarloEngine`: Runner for robustness simulations (shuffling, noise).
- `MetricsCalculator`: Unified tool for evaluating trading performance.
- `BinanceDownloader`: Interface for fetching OHLCV data.

### Generating Documentation

To generate comprehensive HTML documentation from the source code, we recommend using `pdoc3`:

```bash
# Install tool
uv add pdoc3 --dev

# Generate docs
uv run pdoc src/monte_neo -o docs/api/
```

Documentation will be available in the `docs/api/` directory.
