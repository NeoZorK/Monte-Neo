# Testing

## Running Tests

We use `pytest` with `pytest-xdist` and `pytest-cov`.

```bash
# Run all tests in parallel
uv run pytest tests -n auto

# Run tests with coverage and ignore warnings
uv run pytest tests -n auto -W ignore --cov=src/monte_neo

# Run specific test file
uv run pytest tests/unit/test_metrics.py
```

## Test Tiers

- **Unit Tests**: Test individual components in isolation (`tests/unit/`).
- **Integration Tests**: Test full workflows (`tests/integration/`).
- **Stress Tests**: Performance and memory usage checks (`tests/stress/`).

## Tips
- Use `-n auto` to utilize all CPU cores for testing.
- Use `-W ignore` to suppress deprecation warnings from third-party libraries (like `websockets`).
