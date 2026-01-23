# User Settings

Monte-Neo can be configured via environment variables and a YAML config file.

## Environment Variables

Create a `.env` file in the root directory:

```bash
# Binance API (Optional)
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here

# Paths
MONTE_NEO_DATA_DIR=./data

# Performance
MONTE_NEO_WORKERS=auto  # Use all available CPU cores
MONTE_NEO_LOG_LEVEL=INFO
```

## Configuration File (YAML)

Settings can also be defined in `config.yaml`:

```yaml
data:
  symbol: BTCUSDT
  timeframe: 1h

metrics:
  profit_factor: 2.0
  sharpe_ratio: 1.0
  max_drawdown: 0.20

monte_carlo:
  iterations: 1000
```
