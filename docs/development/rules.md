# 📜 Monte-Neo Rules

## Authorship (public repositories)

- Every commit, PR, comment and release on public repositories is authored as **Rostyslav Shcherbyna**
  (`63606118+NeoZorK@users.noreply.github.com`).
- No AI co-author trailers, session links or "Generated with" footers. See root `CLAUDE.md`.

## Language and publication (mandatory)

- Everything in a public repository is in **English only**: code, comments, docs, issues, PRs, commits, releases.
- Private working files live in `docs/internal/`, `scripts/internal/` and `tests/internal/`, which are in `.gitignore`. They are never committed, pushed or linked from public files.
- Before every commit run `git grep -nP "(*UTF)[\x{0400}-\x{04FF}]{3,}"`: any match in a tracked file is a mistake to fix.

## Coding Standards

- **Files < 300 lines**: If a file grows larger, split it into sub-modules.
- **Type Hints**: Mandatory for all function signatures and complex variables.
- **Docstrings**: Google Style `"""Docstring"""` for all public methods and classes.
- **Testing**: Every new feature must have at least one unit test.

## Documentation

- Always update `docs/docs-map.md` when adding, moving, or removing files. **This is mandatory.**
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

- Centralized in `src/monte_neo/_version.py`; every place that names the release must match it
  (`tests/unit/test_maintenance.py::test_version_is_the_same_everywhere`).
- Semantic versions: a **feature release** raises the minor (or major) version (`v0.35.0` -> `v0.36.0`);
  a **patch release** raises the patch version (`v0.35.0` -> `v0.35.1`) and carries only bug fixes
  or security fixes.

## Release cadence

- **No limit on how often releases are published.** Feature releases, patch releases and security
  fixes go out at any time (the owner cancelled the earlier "2 feature releases a day" rule on 2026-09-29).
- Every release still needs the owner's explicit approval, and CI must be green on the merged commit.
