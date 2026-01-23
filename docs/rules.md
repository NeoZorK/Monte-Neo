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

## Versioning

- Centralized in `src/monte_neo/_version.py`.
- Pattern: `v0.0.1` -> `v0.0.2` -> `v0.0.3` (Patch increments during Alpha).
