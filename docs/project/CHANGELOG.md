# Changelog

All notable releases are documented here.
Version source of truth: `src/monte_neo/_version.py`.

## [v0.0.8] — 2026-09-13

### Added
- Professional fee-aware bar backtest engine (`monte_neo.backtest`):
  next-bar fills, commission/slippage bps, cash/position/equity,
  SMA sweep with the same `ExecutionModel`, optional `ReplayBarSource`
  mid-price feeder (no Redis on hot path)
- Docs: `docs/project/backtest_engine.md`
- Unit / integration / stress / performance tests for the new engine

### Notes
- ClaimBound D001 Type C remains a specialized SMA kernel gate; this package
  path is for matched-semantics peer races (private or future D002).

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
