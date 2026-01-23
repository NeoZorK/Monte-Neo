# Development Setup

## Prerequisites

- Python 3.11 or higher
- Git
- Docker (optional, for containerized development)

## Initial Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/NeoZorK/Monte-Neo.git
   cd Monte-Neo
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install in editable mode**:
   ```bash
   pip install -e "."
   pip install -e ".[dev]"
   ```

## Development Workflow

- **Branching**: Use `vX.Y.Z` branches for development.
- **Linting**: Use `ruff` and `black` for code formatting.
- **Testing**: Run `pytest` before submitting changes.
- **Versioning**: Update `src/monte_neo/_version.py` for new releases.
