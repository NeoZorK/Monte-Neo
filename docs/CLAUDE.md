# CLAUDE.md - AI Assistant Guide

## Project Overview

Monte-Neo is a Monte Carlo indicator generator framework for creating robust trading indicators. The core goal is to generate indicators that pass rigorous statistical tests for profitability and robustness.

## Key Commands

```bash
# Run the CLI
python -m monte_neo

# Run tests
pytest tests/ -v --cov=src/monte_neo

# Run specific module
python -m monte_neo.data.downloader --symbol BTCUSDT --timeframe 1h

# Docker headless
docker-compose run monte-neo generate --config config.yaml
```

## Architecture

### Core Modules

- **`src/monte_neo/core/`** - Indicator generator and optimizer
- **`src/monte_neo/data/`** - Binance downloader, Parquet storage
- **`src/monte_neo/monte_carlo/`** - MC engine, shuffling, noise, sensitivity
- **`src/monte_neo/metrics/`** - Trading metrics calculator
- **`src/monte_neo/cli/`** - Interactive terminal interface

### Design Principles

1. **Files < 300 lines** - Split larger modules
2. **Type hints everywhere** - Full typing support
3. **Docstrings** - Google style for all public APIs
4. **Tests first** - Write tests before implementation

## Versioning Strategy

The project uses semantic versioning with a `v` prefix. Version increments follow a patch-level pattern for initial development: `v0.0.1` → `v0.0.2` → `v0.0.3`, etc.

- **Primary version source**: `src/monte_neo/_version.py`
- **How to increment**:
  1. Update `__version__` string in `src/monte_neo/_version.py`.
  2. The version will automatically propagate to `pyproject.toml`, CLI banner, and CLI `--version` output.
  3. Tag the commit with the new version: `git tag v0.0.2`.


```python
# Imports order
from __future__ import annotations

import stdlib
from typing import TYPE_CHECKING

import third_party
import numpy as np
import pandas as pd

from monte_neo.module import local

if TYPE_CHECKING:
    from monte_neo.types import IndicatorConfig
```

### Naming

- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

### Error Handling

```python
from monte_neo.exceptions import (
    DataDownloadError,
    InsufficientDataError,
    MetricNotMetError,
)

# Always specific exceptions, never bare except
try:
    data = download_data(symbol)
except DataDownloadError as e:
    logger.error(f"Failed to download: {e}")
    raise
```

## Key Files to Know

| File | Purpose |
|------|---------|
| `core/generator.py` | Main indicator generation logic |
| `monte_carlo/engine.py` | Monte Carlo simulation runner |
| `metrics/calculator.py` | All trading metrics |
| `cli/app.py` | CLI entry point |
| `cli/menu.py` | Interactive menu system |

## Testing

```bash
# Unit tests only
pytest tests/unit/ -v

# With coverage
pytest --cov=src/monte_neo --cov-report=html

# Specific test
pytest tests/unit/test_metrics.py -v -k "test_profit_factor"
```

## Common Tasks

### Adding a New Metric

1. Create in `src/monte_neo/metrics/`
2. Add to `MetricsCalculator` in `calculator.py`
3. Add CLI option in `cli/menu.py`
4. Write tests in `tests/unit/test_metrics.py`

### Adding a Monte Carlo Method

1. Create in `src/monte_neo/monte_carlo/`
2. Register in `engine.py`
3. Add checkbox in CLI menu
4. Write tests

## Performance Notes

- Use `numba` JIT for hot paths in metrics
- Parquet format for data storage (3-5x faster than CSV)
- `multiprocessing` for MC iterations
- Avoid pandas in tight loops
