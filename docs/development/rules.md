# Rules and Conventions

## Coding Standards

- **Files < 300 lines**: If a file grows larger, split it into sub-modules.
- **Type Hints**: Mandatory for all function signatures and complex variables.
- **Docstrings**: Google Style `"""Docstring"""` for all public methods and classes.
- **Testing**: Every new feature must have at least one unit test.

## Documentation

- Always update `docs/INDEX.md` when adding new files.
- Keep `ROADMAP.md` up to date with completed tasks.
- Document complex mathematical logic in the code and `docs/api-documentation.md`.

## Dependency Management

- **UV-Only**: All dependency additions and environment syncs must be done via `uv`.
- **Lockfile**: Never manually edit `uv.lock`. Allow `uv sync` to manage it.

## Performance Standards

- **Vectorization**: Avoid explicit Python loops for data processing. Use NumPy/Pandas vectorization.
- **Numba for Math**: If a loop is unavoidable (e.g., path-dependent metrics like Drawdown), use `@njit` from Numba.
- **Async/Parallel**: IO-bound tasks should be async or multi-threaded; CPU-bound tasks (MC) must be multi-processed.

## Versioning

- Centralized in `src/monte_neo/_version.py`.
- Pattern: `v0.0.1` -> `v0.1.0` -> `v1.0.0` (following Semantic Versioning).
