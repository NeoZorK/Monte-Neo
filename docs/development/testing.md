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

## Full Verification Suite

For a comprehensive check of the entire system, including static analysis, benchmarks, and hardware-specific tests, use the full test suite script:

```bash
uv run scripts/run_full_test_suite.sh
```

This script executes:
1.  **Environment Check**: Validates system readiness.
2.  **Static Analysis**: Runs Ruff (linter) and Mypy (type checker).
3.  **Core Tests**: Unit, Integration, and Stress tests via pytest.
4.  **Hardware Tests**: Metal/GPU pipeline verification.
5.  **Benchmarks**: Performance testing for indicators and Monte Carlo engines.
6.  **Metrics Verification**: Ensures mathematical correctness of result calculations.
7.  **Visualization**: Generates stress test summary plots.
8.  **Production Pipeline**: Runs a simulated full production run.
9.  **Docker Build**: Verifies the containerization process.

## Test Tiers

- **Unit Tests**: Test individual components in isolation (`tests/unit/`).
- **Integration Tests**: Test full workflows (`tests/integration/`).
- **Stress Tests**: Performance and memory usage checks (`tests/stress/`).

## Tips
- Use `-n auto` to utilize all CPU cores for testing.
- Use `-W ignore` to suppress deprecation warnings from third-party libraries (like `websockets`).

## Fuzzing and property tests

- `tests/fuzz/` holds Hypothesis tests of the file-facing code: certificate parsing, table loaders (CSV and parquet), signal
  arrays, strategy lint, certificate signatures. The contract is a result or a `ValueError`, never another exception.
- `tests/unit/test_core_properties.py` states invariants of the statistics (the Deflated Sharpe never rises with more
  trials, PSR ignores the scale of returns, PBO and the Reality Check ignore row order) and of the look-ahead probes
  (price scaling and column order do not change the verdict).
- `tests/stress/test_core_stress.py` has size and damage tests with generous time limits (marker `performance`); set
  `MONTE_NEO_STRESS_1M=1` to also verify a million bars (several minutes).
- `.clusterfuzzlite/` has coverage-guided atheris targets. They are not run by CI yet: copy
  `.github/cflite-workflow.yml.example` to `.github/workflows/cflite.yml` after pinning the two actions to commit SHAs.
