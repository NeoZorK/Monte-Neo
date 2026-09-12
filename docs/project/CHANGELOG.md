# Changelog

All notable releases are documented here.
Version source of truth: `src/monte_neo/_version.py`.

## [v0.0.7] — 2026-09-12

First formal GitHub Release. Canonical development branch is **`main`**
(older branches named `v0.0.1` … `v0.0.6` are historical archives only).

### Added
- Public ClaimBound fair-race helpers (`monte_neo.fair_race`) and CLI `monte-neo-fair-race`
- Type B CPU fallback when Metal native extension is unavailable
- Unit tests for fair-race helpers and license/version doc sync

### Changed
- License metadata aligned to **MIT** (`LICENSE` + `pyproject.toml`)
- Docs / INDEX / ROADMAP synchronized to **v0.0.7**

### Security
- Pillow pinned to `>=12.3.0` on the release line (Dependabot alerts cleared)

### Notes
- Install: `pip install "monte-neo @ git+https://github.com/NeoZorK/Monte-Neo.git@v0.0.7"`
- Or: `uv add "monte-neo @ git+https://github.com/NeoZorK/Monte-Neo.git@v0.0.7"`
