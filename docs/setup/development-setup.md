# Development Setup

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (highly recommended)
- Git
- Docker (optional)
- macOS Apple Silicon for Metal native extensions

## Initial Setup

1. **Clone from NeoZorK gitserver** (private):

   ```bash
   git clone /Users/rostsh/git-server/NeoZorK/Monte-Neo.git
   cd Monte-Neo
   ```

   From LAN:

   ```bash
   git clone ssh://rost@2014/Users/rost/git-server/NeoZorK/Monte-Neo.git
   cd Monte-Neo
   ```

2. **Sync the environment**:

   ```bash
   uv sync
   ```

3. **Build native extensions** (Metal + pybind11, macOS):

   ```bash
   uv run bash scripts/build_native.sh
   uv run python verify_hardware.py
   ```

## Development Workflow

- **Testing**: `uv run pytest tests -n auto`
- **Linting**: `uv run ruff check` and `uv run black .`
- **Pre-commit**: `uv run pre-commit install`

## Remotes (R-REMOTE)

- `origin` → `/Users/rostsh/git-server/NeoZorK/Monte-Neo.git`
- `lan` → `ssh://rost@2014/Users/rost/git-server/NeoZorK/Monte-Neo.git` (optional)

Push tags with branches: `git push origin --all && git push origin --tags`
