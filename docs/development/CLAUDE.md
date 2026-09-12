# 🤖 Monte-Neo Development (v0.0.7)

## Project Overview
Monte-Neo is a Monte Carlo indicator generator framework.

## Key Commands
```bash
# Env setup
uv sync

# Run CLI
uv run monte-neo

# Run Full Test Suite (Recommended)
./scripts/run_full_test_suite.sh

# Run Tests manually
uv run pytest tests -n auto -W ignore --cov=src/monte_neo

# Docker
docker-compose -f docker/docker-compose.yml up -d
docker-compose -f docker/docker-compose.yml exec monte-neo bash
```

## Architecture
- `src/monte_neo/core/`: Generator & optimizer (including 3D GPU acceleration)
- `src/monte_neo/core/optimization/`: Production Gate, certification, and stress testing
- `src/monte_neo/data/`: Downloader & storage
- `src/monte_neo/monte_carlo/`: Shuffling, noise, sensitivity, walk-forward
- `src/monte_neo/metrics/`: Performance calculation modules
- `src/monte_neo/cli/`: Interactive interface

## Key Technologies
- **MLX/Metal**: 3D GPU acceleration for population evaluation (up to 125x speedup).
- **Numba**: JIT-optimized metrics and SL/TP calculation.
- **Production Gate**: Multi-stage robustness certification pipeline.

## Design Principles
1. **Files < 300 lines**: Split larger modules.
2. **Type Hints**: Mandatory for all signatures.
3. **Docstrings**: Google Style required.
4. **UV-First**: All commands and environment management must use `uv`.
5. **No Placeholders**: All implementation details must be functional.
6. **Maintain Index**: Always update `docs/INDEX.md` when files change.

## Versioning Strategy
Primary version source: `src/monte_neo/_version.py`.
Pattern: `v0.0.1` -> `v0.0.2` -> ... -> `v0.0.7`.

## Coding Style
- Imports: standard, third-party, local. `from __future__ import annotations` required.
- Naming: `PascalCase` for classes, `snake_case` for functions/variables.
- Error Handling: Specific exceptions only.

## Testing
- **Unit**: `tests/unit/`
- **Integration**: `tests/integration/`
- **Stress**: `tests/stress/` (Memory/CPU performance)
