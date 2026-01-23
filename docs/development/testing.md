# Testing

## Running Tests

We use `pytest` for all testing.

```bash
# Run all unit tests
pytest tests/unit/

# Run tests with coverage report
pytest --cov=src/monte_neo --cov-report=term-missing
```

## Test Structure

- **Unit Tests**: Test individual components in isolation (`tests/unit/`).
- **Integration Tests**: Test full workflows (e.g., download -> generate -> visualize).
- **Fixtures**: Shared data and setups are in `tests/conftest.py`.

## Adding Tests

When adding a new metric or MC method, create a corresponding test file in `tests/unit/` using the prefix `test_`.
