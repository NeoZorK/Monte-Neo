# Monte-Neo

🎲 **Monte Carlo Indicator Generator Framework**

A professional Python framework for generating robust and profitable trading indicators using Monte Carlo simulation methods.

## Features

- 🎯 **Target-Based Generation**: Define metrics (Profit Factor, Sharpe, Max DD) and generate matching indicators
- 🧠 **Smart Pipeline Optimizer**: Adaptive search logic that adjusts parameters and timeframes based on failures
- 🏆 **Global Leadership Pipeline**: Fully automated end-to-end discovery with real-time status monitoring
- 🚀 **Extreme GPU Acceleration**: Direct Metal Shaders (C++) and MLX support (>780k ops/sec on Apple Silicon)
- 💎 **Low-Precision Computing**: Support for Float8 (E4M3/E5M2) for 4x memory bandwidth savings
- 🧙 **Sequential "Wizard" Mode**: Step-by-step validation with detailed feedback and advice
- 🧪 **Custom Strategy Lab**: Test your own formulas against professional stress tests
- 📜 **Robustness Certificate**: Production-ready verification proof
- 🔀 **Monte Carlo Methods**: Shuffling, noise injection, sensitivity analysis (±10%), walk-forward
- 📊 **Binance Integration**: Download OHLCV data in fast Parquet format
- 🖥️ **Interactive CLI**: Arrow-key navigation, progress bars, color output
- 🐳 **Docker Support**: Headless mode for server deployment
- ⚡ **High Performance**: Parallel processing, optimized data handling
- 🛡️ **Reliability First**: Core modules (Backtesting, Metrics, Monte Carlo) covered by ~100% unit tests

## Quick Start

```bash
# 1. Install & Setup Environment
uv sync

# 2. Run CLI
uv run monte-neo

# 3. Run All Tests (300+)
uv run pytest tests -n auto

# 4. Generate Coverage Report
uv run coverage run -m pytest && uv run coverage report
```

## Running with Docker

The framework is fully dockerized and supports both interactive and headless modes.

### 1. Start Persistent Container
This starts the container in the background and keeps it alive:
```bash
docker-compose -f docker/docker-compose.yml up -d
```

### 2. Enter Container & Run CLI
To interact with the generator inside Docker:
```bash
# Enter the shell
docker-compose -f docker/docker-compose.yml exec monte-neo bash

# Run the interactive CLI from inside
uv run monte-neo
```

### 3. Persistent Data
All data remains persistent between restarts:
- **OHLCV Data**: Stored in `./data/raw` and `./data/processed`
- **Results**: Optimized indicators and charts are saved to `./data/results`
These directories are mapped to your local machine via volumes.

### 4. Cleanup
To stop and remove the container:
```bash
docker-compose -f docker/docker-compose.yml down
```

## Workflow

1. **Download Data** → Select symbol, timeframe, date range from Binance
2. **Set Metrics** → Define target (e.g., Profit Factor > 2, Max DD < 20%)
3. **Configure MC** → Select methods: shuffling, noise, sensitivity, walk-forward
4. **Generate** → Run 100,000+ iterations to find robust indicator
5. **Visualize** → View chart with entries, exits, and all metrics

## Available Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Winrate | 40-60% | Win percentage |
| Profit Factor | > 2.0 | Gross profit / loss |
| Sharpe Ratio | > 1.0 | Risk-adjusted return |
| Sortino Ratio | > 1.5 | Downside-adjusted |
| Max Drawdown | < 20% | Max capital decline |
| Recovery Factor | > 2.0 | Profit / Max DD |
| Calmar Ratio | > 0.5 | Annual / Max DD |

## Project Structure

```
Monte-Neo/
├── src/monte_neo/     # Main package
│   ├── core/          # Generator engine
│   ├── data/          # Binance downloader
│   ├── monte_carlo/   # MC methods
│   ├── metrics/       # Trading metrics
│   ├── cli/           # Interactive CLI
│   └── visualization/ # Charts
├── tests/             # Unit & integration tests
├── docs/              # Documentation
└── scripts/           # Utility scripts
```

## Requirements

- Python 3.11+
- See `pyproject.toml` for dependencies

## License

Proprietary — NeoZorK. See [LICENSE](LICENSE) and [docs/COMMERCIAL_RU.md](docs/COMMERCIAL_RU.md).
Not open source. Clone only from NeoZorK gitserver.
