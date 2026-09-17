# Contributing

Thanks for helping improve Monte-Neo. Keep changes small, local-Mac friendly, and free of peer-product names in this tree.

## Quick path

1. Fork / clone, Python **3.11+**
2. `uv sync --extra apple --extra plot --extra data --group dev` (omit `--extra apple` on Linux CI)
3. Branch from `main`: `feat/…` or `fix/…`
4. `uv run ruff check .` and `uv run pytest tests/unit -W ignore`
5. Open a PR against `main` — CI `test` must be green

## What belongs here

- Research-bar export, holdout, policy heuristics, Metal/Numba performance, docs clarity
- MIT-compatible code and docs only

## What does not

- Live multi-venue bot-ops as the primary claim
- Naming rival frameworks/authors in public code/docs/README
- Copying private harness / Evidence content into this tree without explicit permission

## Versioning (Swiss clock)

- Single source: `src/monte_neo/_version.py` (`vX.Y.Z`)
- Keep in lockstep: `CHANGELOG`, `ROADMAP`, `README` current line, `docs/INDEX.md`
- Releases: GitHub Release tag `vX.Y.Z` → OIDC Publish to PyPI

## Docs site

MkDocs Material under `docs/`. Push to `main` with `docs/**` or `mkdocs.yml` changes runs the Docs workflow → https://neozork.github.io/Monte-Neo/

## Code style

- Ruff (`I` import sorting); prefer small modules
- Unit tests under `tests/unit/`; coverage gates apply to non-omitted packages
- No secrets in the tree (`.env` stays local)

## Issues

Use GitHub issue templates (bug / feature). Include OS, Python version, `monte-neo` version, and a minimal repro when reporting bugs.

## Security

Report vulnerabilities privately via [SECURITY.md](https://github.com/NeoZorK/Monte-Neo/blob/main/SECURITY.md) (GitHub Security Advisories when available). Do not open public issues for exploitable bugs.
