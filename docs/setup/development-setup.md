# Development Setup

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (highly recommended)
- Git
- Docker (optional)

## Initial Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/NeoZorK/Monte-Neo.git
   cd Monte-Neo
   ```

2. **Sync the environment**:
   Using `uv` is the fastest and most reliable way to set up the project:
   ```bash
   uv sync
   ```
   *This command creates a virtual environment in `.venv` and installs all dependencies including development tools.*

## Development Workflow

- **Testing**: Run tests frequently using `uv run pytest`.
- **Parallel Testing**: Use `uv run pytest -n auto` for fast execution.
- **Linting & Formatting**: `uv run ruff check` and `uv run black .`.
- **Pre-commit**: It is recommended to install pre-commit hooks: `uv run pre-commit install`.

