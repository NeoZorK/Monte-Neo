# Branching and versioning

- **Canonical branch:** `main` (default on GitHub).
- **Version source:** `src/monte_neo/_version.py` (`vX.Y.Z` with leading `v`).
- **Releases:** annotated git tags + GitHub Releases (first formal release: `v0.0.7`).
- **Historical branches** named `v0.0.1` … `v0.0.6` are archives from before `main`
  became the default. Do not treat those branch names as the current package version.
- Changes land via pull request; sole maintainer may merge without review approval.
  Required status check: `test`.
