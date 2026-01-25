# tech-stack.md - Technology Stack

## Core Language

### Python 3.11+
Primary language for all modules.

**Why Python:**
- Rich data science ecosystem (pandas, numpy)
- Excellent for prototyping and iteration
- Strong typing support (mypy)
- Cross-platform

### C++ (pybind11)
Native extensions for performance-critical trade extraction and metrics calculation.

### MLX (Apple Silicon GPU)
Leverages the M1/M2/M3 GPU and Unified Memory for massive parallel Monte Carlo simulations.

---

## Package Management

### [uv](https://github.com/astral-sh/uv)
Extremeley fast Python package manager and project manager. Replaces `pip`, `pip-tools`, and `venv`.

---

## Dependencies

### Data & Computation

| Package | Version | Purpose |
|---------|---------|---------|
| `numpy` | >=1.24 | Numerical computing |
| `pandas` | >=2.0 | Data manipulation |
| `pyarrow` | >=14.0 | Parquet I/O |
| `numba` | >=0.58 | JIT compilation (Fallback) |
| `mlx` | >=0.11 | GPU acceleration (Apple Silicon) |
| `pybind11`| >=2.10 | C++ Python bindings |

### Trading & Finance

| Package | Version | Purpose |
|---------|---------|---------|
| `python-binance` | >=1.0.17 | Binance API |
| `ta` | >=0.10 | Technical indicators |

### CLI & Visualization

| Package | Version | Purpose |
|---------|---------|---------|
| `rich` | >=13.0 | Terminal formatting |
| `questionary` | >=2.0 | Interactive prompts |
| `plotext` | >=5.2 | Terminal charts |
| `mplfinance` | >=0.12 | Candlestick charts |

### Development

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | >=7.4 | Testing |
| `pytest-xdist`| >=3.3 | Parallel testing (-n) |
| `pytest-cov` | >=4.1 | Coverage |
| `mypy` | >=1.5 | Type checking |
| `ruff` | >=0.1 | Linting |
| `black` | >=23.0 | Formatting |

---

## Platform Support

### Primary
- **macOS** (Apple Silicon & Intel)
- **Linux** (Ubuntu 22.04+, Debian 12+)
- **Windows** (10/11 with WSL2 or native)

### Docker
- **Base Image**: `python:3.11-slim`
- **Headless Mode**: Full CLI without display
- **Volume Mounts**: Data persistence

---

## Performance Targets

| Operation | Target |
|-----------|--------|
| Data download (1 year) | < 30s |
| Sample generation | < 1s |
| 10,000 MC iterations | < 5s (GPU) |
| 100,000 MC iterations | < 60s (GPU) |
| Metrics calculation | < 1ms (C++) |

---

## Configuration

### Environment Variables

```bash
# .env
BINANCE_API_KEY=optional_for_public_data
BINANCE_API_SECRET=optional_for_public_data
MONTE_NEO_DATA_DIR=/path/to/data
MONTE_NEO_LOG_LEVEL=INFO
MONTE_NEO_WORKERS=auto  # or number
```

### Config File (YAML)

```yaml
# config.yaml
data:
  symbol: BTCUSDT
  timeframe: 1h
  source: binance

metrics:
  profit_factor: 2.0
  max_drawdown: 0.20
  sharpe_ratio: 1.0

monte_carlo:
  iterations: 100000
  methods:
    - shuffling
    - noise
    - sensitivity
    - walk_forward
```
