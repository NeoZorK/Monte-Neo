# Development Setup

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (highly recommended)
- Git
- Docker (optional)
- macOS Apple Silicon for Metal native extensions

## Initial Setup

1. **Clone the repository**:

   ```bash
   git clone https://github.com/NeoZorK/Monte-Neo.git
   cd Monte-Neo
   ```

2. **Sync the environment**:

   ```bash
   uv sync
   ```

3. **Build native extensions** (Metal + pybind11, macOS):

   ```bash
   uv run bash scripts/build_native.sh
   uv run python scripts/verify_hardware.py
   ```

## Development Workflow

- **Testing**: `uv run pytest tests -n auto`
- **Linting**: `uv run ruff check` and `uv run black .`
- **Pre-commit**: `uv run pre-commit install`
