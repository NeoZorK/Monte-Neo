# User Settings

Monte-Neo can be configured via environment variables, a YAML config file, and CLI arguments.

## Environment Variables

Create a `.env` file in the root directory for persistent settings:

```bash
# BINANCE CREDENTIALS
# Optional: Only needed if you want to use private API endpoints or avoid rate limits
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here

# PROJECT PATHS
# Where OHLCV data and results will be stored
MONTE_NEO_DATA_DIR=./data

# PERFORMANCE & LOGGING
# Number of CPU workers for Monte Carlo (default: auto/all cores)
MONTE_NEO_WORKERS=auto
# Options: DEBUG, INFO, WARNING, ERROR
MONTE_NEO_LOG_LEVEL=INFO

# DISPLAY SETTINGS
# Set to 'false' to disable terminal charts (plotext) if causing issues
MONTE_NEO_ENABLE_CHARTS=true
```

## Configuration File (`config.yaml`)

For headless mode or reproducible generations, use a YAML file:

```yaml
# Data source configuration
data:
  symbol: BTCUSDT
  timeframe: 1h
  days: 365

# Target metrics to stop generation
metrics:
  profit_factor: 2.5
  sharpe_ratio: 1.5
  max_drawdown: 0.15
  winrate: 0.55

# Monte Carlo robustness settings
monte_carlo:
  iterations: 10000
  use_shuffling: true
  use_noise: true
  use_sensitivity: true
  use_walk_forward: true

# Risk Management
risk_management:
  use_sl_tp: true
  stop_loss_pct: 1.0
  take_profit_pct: 2.0  # 2:1 Risk Ratio
```

## Storage Location

By default, the project uses the following structure under `MONTE_NEO_DATA_DIR`:
- `/raw`: Original Parquet files from Binance.
- `/processed`: Filtered and sampled data used for generation.
- `/results`: Finalized indicator code and performance reports.

