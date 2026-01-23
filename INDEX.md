# INDEX.md - File Index

Complete list of all project files with paths and purposes.

## Root Files

| File | Purpose |
|------|---------|
| `README.md` | Main project documentation |
| `INDEX.md` | This file index |
| `LICENSE` | MIT License |
| `pyproject.toml` | Python package config |
| `.gitignore` | Git ignore rules |
| `.env.example` | Environment template |

## Documentation (`docs/`)

| File | Purpose |
|------|---------|
| `docs/CLAUDE.md` | AI assistant guide |
| `docs/ROADMAP.md` | Development roadmap |
| `docs/tech-stack.md` | Technology stack docs |

## Docker (`docker/`)

| File | Purpose |
|------|---------|
| `docker/Dockerfile` | Docker build |
| `docker/docker-compose.yml` | Docker compose |

## Source Code (`src/monte_neo/`)

| File | Purpose |
|------|---------|
| `_version.py` | Single source of truth for version (v0.0.1) |
| `__init__.py` | Package exports |

### Core (`src/monte_neo/core/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports |
| `generator.py` | Main indicator generator |
| `optimizer.py` | Parameter optimization |
| `validator.py` | Overfitting validation |

### Data (`src/monte_neo/data/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports |
| `downloader.py` | Binance data download |
| `storage.py` | Parquet storage |
| `sampler.py` | Sample generation |

### Monte Carlo (`src/monte_neo/monte_carlo/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports |
| `engine.py` | Main MC engine |
| `shuffler.py` | Data shuffling |
| `noise.py` | Noise injection |
| `sensitivity.py` | ±10% parameter analysis |
| `walk_forward.py` | Rolling walk-forward |

### Metrics (`src/monte_neo/metrics/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports |
| `calculator.py` | Unified calculator |
| `profit_factor.py` | Profit Factor metric |
| `sharpe.py` | Sharpe/Sortino ratios |
| `drawdown.py` | Drawdown metrics |
| `winrate.py` | Winrate & expectancy |

### Indicators (`src/monte_neo/indicators/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports |
| `base.py` | Base indicator class |
| `technical.py` | Technical indicators |
| `custom.py` | Custom builder |

### CLI (`src/monte_neo/cli/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports |
| `app.py` | Main CLI app |
| `menu.py` | Interactive menu |
| `progress.py` | Progress bar |
| `styles.py` | Terminal styles |

### Visualization (`src/monte_neo/visualization/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports |
| `charts.py` | Chart generation |
| `trades.py` | Trade visualization |
| `metrics.py` | Metrics display |

### Utils (`src/monte_neo/utils/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports |
| `config.py` | Configuration |
| `logger.py` | Logging setup |
| `parallel.py` | Parallel processing |

## Tests (`tests/`)

| Path | Purpose |
|------|---------|
| `conftest.py` | Pytest fixtures |
| `unit/` | Unit tests |
| `integration/` | Integration tests |

## Scripts (`scripts/`)

| File | Purpose |
|------|---------|
| `download_data.py` | Data download helper |
| `benchmark.py` | Performance benchmarks |
| `setup_env.sh` | Environment setup |

## Data (`data/`) - Gitignored

| Path | Purpose |
|------|---------|
| `raw/` | Raw downloaded data |
| `processed/` | Processed samples |
| `results/` | Generation results |
