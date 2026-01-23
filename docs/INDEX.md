# Project Index

A simplified guide to the Monte-Neo file structure.

## Format: [file path] - [description]

### Root Configuration
- README.md - Main project documentation
- pyproject.toml - Python package configuration and dependencies
- uv.lock - Lockfile for consistent environment management
- LICENSE - MIT License
- .gitignore - Git exclusion rules
- .env.example - Environment variables template

### Project Information (docs/project/)
- docs/project/project-idea.md - The philosophy and vision behind Monte-Neo
- docs/project/vision.md - Original design goals and core principles
- docs/project/project-structure.md - Deep dive into physical directory layout
- docs/project/features.md - Detailed overview of framework features
- docs/project/ROADMAP.md - Development roadmap and milestones
- docs/project/tech-stack.md - Technology stack and performance targets

### Setup & Configuration (docs/setup/)
- docs/setup/installation.md - Installation instructions for users and developers
- docs/setup/development-setup.md - Guide for setting up the dev environment
- docs/setup/auth.md - Authentication and Binance API key setup
- docs/setup/user-settings.md - Configuration and environment variable guide

### Development (docs/development/)
- docs/development/rules.md - Project-specific rules and conventions
- docs/development/testing.md - Testing strategy and execution guide
- docs/development/performance.md - Performance notes and benchmarks
- docs/development/external-libs.md - List and purpose of external dependencies
- docs/development/api-documentation.md - Guide to API and code documentation
- docs/development/CLAUDE.md - AI assistant guide and coding conventions

### Guides & Examples (docs/guides/, docs/examples/)
- docs/guides/quick-start.md - 3-step guide to get started
- docs/examples/README.md - Standalone script examples (Placeholder)
- docs/api/README.md - API reference (Placeholder)

### Docker (docker/)
- docker/Dockerfile - Multi-stage Docker build using uv
- docker/docker-compose.yml - Docker Compose service definitions

### Source Code (src/monte_neo/)
- src/monte_neo/_version.py - Central version management (v0.0.1)
- src/monte_neo/__init__.py - Main package entry point

#### Core Engine (core/)
- src/monte_neo/core/__init__.py - Core exports
- src/monte_neo/core/generator.py - Main indicator generation logic
- src/monte_neo/core/optimizer.py - Parameter optimization strategies
- src/monte_neo/core/validator.py - Overfitting and robustness validation

#### Data Handling (data/)
- src/monte_neo/data/__init__.py - Data module exports
- src/monte_neo/data/downloader.py - Binance OHLCV data downloader
- src/monte_neo/data/storage.py - Efficient Parquet storage handler
- src/monte_neo/data/sampler.py - Bootstrap and synthetic data sampling

#### Monte Carlo (monte_carlo/)
- src/monte_neo/monte_carlo/__init__.py - MC module exports
- src/monte_neo/monte_carlo/engine.py - Main simulation execution engine
- src/monte_neo/monte_carlo/shuffler.py - Return and block shuffling methods
- src/monte_neo/monte_carlo/noise.py - Noise injection and slippage simulation
- src/monte_neo/monte_carlo/sensitivity.py - Parameter sensitivity analysis
- src/monte_neo/monte_carlo/walk_forward.py - Rolling walk-forward validation

#### Metrics (metrics/)
- src/monte_neo/metrics/__init__.py - Metrics module exports
- src/monte_neo/metrics/calculator.py - Unified trading metrics calculator
- src/monte_neo/metrics/profit_factor.py - Profit Factor calculation
- src/monte_neo/metrics/sharpe.py - Sharpe and Sortino ratio metrics
- src/monte_neo/metrics/drawdown.py - Max and average drawdown metrics
- src/monte_neo/metrics/winrate.py - Winrate and expectancy metrics

#### Trading Logic (indicators/)
- src/monte_neo/indicators/__init__.py - Indicator exports
- src/monte_neo/indicators/base.py - Abstract base indicator class
- src/monte_neo/indicators/technical.py - Portfolio of technical indicators
- src/monte_neo/indicators/custom.py - Build-your-own indicator builder

#### Interface (cli/)
- src/monte_neo/cli/__init__.py - CLI module exports
- src/monte_neo/cli/app.py - CLI entry point and argument parsing
- src/monte_neo/cli/menu.py - Interactive arrow-navigation menu
- src/monte_neo/cli/progress.py - Rich progress bars and ETA
- src/monte_neo/cli/styles.py - Terminal styling and themes

#### Visuals (visualization/)
- src/monte_neo/visualization/__init__.py - Viz module exports
- src/monte_neo/visualization/charts.py - Candlestick and signal charting
- src/monte_neo/visualization/trades.py - Trade-by-trade visualization
- src/monte_neo/visualization/metrics.py - Performance metrics dashboard

#### Utilities (utils/)
- src/monte_neo/utils/__init__.py - Utils module exports
- src/monte_neo/utils/config.py - Configuration management
- src/monte_neo/utils/logger.py - Standardized logging setup
- src/monte_neo/utils/parallel.py - Multiprocessing and parallel execution

### Tests (tests/)
- tests/conftest.py - Shared pytest fixtures
- tests/unit/ - Targeted unit tests for all modules
- tests/integration/ - End-to-end workflow tests
- tests/stress/ - Memory and CPU performance stress tests

### Utility Scripts (scripts/)
- scripts/run_full_test_suite.sh - Master verification script (uv + docker)
