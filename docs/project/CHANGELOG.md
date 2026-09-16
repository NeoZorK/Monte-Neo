# Changelog

All notable releases are documented here.
Version source of truth: `src/monte_neo/_version.py`.

## [v0.15.0] — 2026-09-15

### Fixed
- `verify_export_golden` / `verify_golden_vectors`: auto Metal float32 tolerance band when batch resolves to Metal
- Unit metrics: pin Numba path for deterministic `trade_count`; native extract stub via `_get_native`
- Build: pin `hatchling>=1.24,<1.26` so wheels emit Metadata 2.3 (twine-check friendly)
- Packaging: `.gitignore` `/data/` (root only) so `monte_neo.data` is included in wheels

### Packaging / PyPI prep
- `mlx` + PyObjC Metal moved to optional extra **`monte-neo[apple]`** (Linux/CI-friendly wheels)
- Hatch version pattern strips leading `v` for PEP 440 distribution version
- Richer `project` metadata: description, keywords, classifiers, `project.urls`
- `docs/project/PACKAGING.md` — free-only PyPI / TestPyPI checklist

### Docs / examples
- Demo assets: `docs/assets/demo_sma_sweep.png`, `docs/assets/demo_memory_plan.png`
- `examples/export_sma_sweep_quickstart.py` + examples README
- README install notes for `[apple]` and git install

### Notes
- First PyPI upload still gated on TestPyPI + maintainer OK (see PACKAGING.md)
- License remains **MIT**. No peer product names in this tree.

## [v0.14.1] — 2026-09-15

### Fixed
- Research accelerator **no-hang gate**: oversized Metal/MLX workloads fall back to `cpu_numba` instead of blocking forever on GPU wait (e.g. 10M-bar sweeps on 16GB-class hosts)
- Transparent `fallback_reason` when auto demotes Metal (`metal_max_bars_exceeded`, shared-budget, host soft budget)

### Docs
- README: install from GitHub, research export quickstart, advantages, device notes
- `docs/guides/FAQ.md` starter

### Notes
- Env knobs: `MONTE_NEO_RESEARCH_BYTES_BUDGET`, `MONTE_NEO_METAL_SHARED_BYTES_BUDGET`, `MONTE_NEO_METAL_MAX_BARS`
- License remains **MIT**. No peer product names in this tree.

## [v0.14.0] — 2026-09-15

### Added
- `plan_research_bytes` for Apple Silicon 16GB soft budgets / tile hints
- Export depth: `equity_stride`, `include_journal`, optional `memory` on single/batch
- README positioning: local macOS research job vs non-goals (no rival names)

### Notes
- License remains **MIT**. Evidence publication stays permission-gated and out of tree.

## [v0.13.0] — 2026-09-15

### Added
- Research signal factory (`build_sma_cross_grid`): Numba-parallel SMA cross grids
- Sweep/export expose `signal_elapsed_s` + `economics_elapsed_s` (wall includes both)

### Notes
- Default signal device is Numba (exact); MLX signal path remains opt-in.
- No peer product names in this tree. License remains **MIT**.

## [v0.12.0] — 2026-09-14

### Added
- Stable research-bar export API (`export_single` / `export_batch` / `export_sma_sweep` / `research_manifest`)
- Frozen golden vectors (`verify_golden_vectors`) for fee-hurts + batch↔single parity before any external timer
- Timers disclose `includes_signal_build` so harnesses cannot mis-attribute work

### Notes
- No peer product names in this tree. Export is for external honesty harnesses only.
- License remains **MIT**.

## [v0.11.0] — 2026-09-14

### Added
- Research Metal economics: funding, session mask, long_short (Numba golden parity)
- Rewrote stale MLX engine unit tests against current kwargs-only API (no skips)

### Notes
- Evidence publication stays out of this repository.
- License remains **MIT**.

## [v0.10.0] — 2026-09-14

### Added
- Research Metal economics: SL/TP/trail on long/flat next-bar-open (Numba golden parity)
- Parity + perf coverage for Metal stop/trail subset

### Notes
- Funding / session mask / long_short remain Numba-only.
- Evidence publication stays out of this repository and permission-gated.
- License remains **MIT**.

## [v0.9.1] — 2026-09-14

### Removed
- Public evidence-reproduce helpers, CLI entrypoint, and `core/race` optimization surface
- Development race docs that described public evidence reproduce flows

### Notes
- Evidence publication remains permission-gated and lives outside this repository.
- License remains **MIT**.

## [v0.9.0] — 2026-09-14

### Added
- Research bar Metal economics batch (long/flat next-bar-open subset)
- OMS: `BarClock`, `TimeInForce` (GTC/IOC), OCO/bracket helper, honest `max_fill_qty` partials
- OMS: `adapters/replay.py` OHLC replay; accel `BufferPool` + `shader_catalog`
- `device=` on `run_bar_backtest_batch` / `run_sma_sweep` (Metal when eligible, else Numba golden)
- Parity + perf smoke for Metal vs Numba (`fill_fraction` / `leverage` included)

### Notes
- SL/TP/trail/funding/session/long_short remain Numba-only (full ExecutionModel).
- Metal float32 vs Numba float64 uses documented rtol/atol.
- License remains **MIT**. Evidence publication still permission-gated (out of tree).

## [v0.8.0] — 2026-09-14

### Added
- MC Metal/MLX/CPU unified dispatch (`plan_mc_run`) honoring `compute_device` / `use_gpu`
- M1 Pro 16GB-class scenario memory budgets (`plan_scenario_budget`, tile ranges)
- `MCResult.device_used` / `bytes_peak_est` / `accel_plan`; `MCConfig.memory_budget_bytes`
- Docs: `docs/project/mc_accel.md`

### Notes
- Metal-first on Apple Silicon; MLX used when native params are absent but MLX repr exists.
- License remains **MIT**. Evidence publication still permission-gated (out of tree).

## [v0.7.0] — 2026-09-14

### Added
- Metal L2 book-walk dispatch (PyObjC) with Numba float64 golden parity
- `run_l2_walk` / `run_l2_walk_batch` device-aware paths; TickL2Engine uses them
- Unit parity + performance smoke for Metal L2 batch walk

### Notes
- Metal uses float32; parity tests allow documented rtol/atol vs Numba float64.
- License remains **MIT**. Evidence publication still permission-gated (out of tree).

## [v0.6.0] — 2026-09-14

### Added
- Metal OMS batch dispatch (PyObjC) with Numba float64 golden parity
- `run_batch_terminal(device=...)` / `preferred_compute_device` for honest device reports
- MCConfig.`compute_device` + engine `compute_pref` checklist
- Perf smoke for auto Metal/Numba batch path

### Notes
- Metal uses float32; parity tests allow documented rtol/atol vs Numba float64.
- License remains **MIT**. Evidence publication still permission-gated (out of tree).

## [v0.5.0] — 2026-09-14

### Added
- Venue adapters: `PaperExchangeAdapter`, `BinanceAdapter`, `BybitAdapter`
- `make_adapter()` factory + fill reconciliation helper
- Live safety gates: `MONTE_NEO_LIVE_TRADING`, `MONTE_NEO_LIVE_DRY_RUN` (default dry-run)
- `.env.example` keys for Bybit + live flags

### Notes
- Paper mode is default (no network). Live submit without dry-run is blocked in this build.
- License remains **MIT**. Evidence publication still permission-gated (out of tree).

## [v0.4.0] — 2026-09-14

### Added
- Tick/L2 OMS lane: `TickL2Engine`, synthetic ticks, order book, L2 walk
- Numba `walk_book_market` with Python L2 parity tests
- Metal shader scaffold `oms_l2_walk.metal`
- Docs updated for dual research + OMS tick paths

### Notes
- Paper/synthetic books only in this cut (live adapters later).
- License remains **MIT**. Evidence publication still permission-gated (out of tree).

## [v0.3.0] — 2026-09-13

### Added
- Paper OMS lane (`monte_neo.oms`): orders, matching, portfolio netting, blotter
- Accel device select (`cpu_numba` / `metal` / `mlx` / `auto`) for Apple Silicon
- Numba OMS batch helper + Metal shader scaffold (`oms_bar_match.metal`)
- Docs: `docs/project/oms_engine.md`; roadmap rules (silence, Evidence gate, sync)

### Notes
- Research bar engine (`monte_neo.backtest`) unchanged as a separate lane.
- License remains **MIT**.
- No public Evidence publication without maintainer permission after correct private runs.

## [v0.2.0] — 2026-09-13

### Added
- Session mask (block new entries off-session; exits/SL/TP still allowed)
- Funding lite (`funding_bps_per_bar`) and leverage (`leverage >= 1`)
- Shared-cash multi-symbol portfolio (`run_portfolio_shared_cash`)
- Correctness suite: dual-hit SL preference, batch≡single with new knobs

### Notes
- Research bar engine scope unchanged (not a full OMS).
- No public speed evidence until private comparisons complete and user OK.
- License remains **MIT**.

## [v0.1.0] — 2026-09-13

### Added
- Brand logo (`docs/assets/monteneo-logo.png`) and honest GitHub-facing README
- GP bar engine: `StrategySpec` / `run_strategy_backtest`, trail stops, impact_bps,
  partial `fill_fraction`, expanded work checklist
- Docs: clearer scope (research bar engine ≠ full OMS)

### Notes
- License remains **MIT**.

## [v0.0.9] — 2026-09-13

### Added
- `ExecutionModel.sl_pct` / `tp_pct` with H/L exits (SL preferred on dual hit)
- Trade journal + metrics (`sharpe`, `profit_factor`, `win_rate`, max DD)
- `run_bar_backtest_batch` for external signal matrices (shared economics)
- `run_multi_symbol_lite` (independent cash books)
- `run_sma_sweep` now wraps batch (labeled convenience, not D001 kernel)

### Notes
- Costs remain **bps** on this path; older `metrics` helpers may use %.

## [v0.0.8] — 2026-09-13

### Added
- Professional fee-aware bar backtest engine (`monte_neo.backtest`):
  next-bar fills, commission/slippage bps, cash/position/equity,
  SMA sweep with the same `ExecutionModel`, optional `ReplayBarSource`
  mid-price feeder (no Redis on hot path)
- Docs: `docs/project/backtest_engine.md`
- Unit / integration / stress / performance tests for the new engine

### Notes
- Specialized SMA kernel gates for private local protocols remain out of scope; this package
  path is for matched-semantics peer races (private or future D002).

## [v0.0.7] — 2026-09-12

First formal GitHub Release. Canonical development branch is **`main`**
(older branches named `v0.0.1` … `v0.0.6` are historical archives only).

### Added
- Public evidence-reproduce helpers and CLI (later removed in v0.9.1)
- Type B CPU fallback when Metal native extension is unavailable
- Unit tests for license/version doc sync

### Changed
- License metadata aligned to **MIT** (`LICENSE` + `pyproject.toml`)
- Docs / INDEX / ROADMAP synchronized to **v0.0.7**

### Security
- Pillow pinned to `>=12.3.0` on the release line (Dependabot alerts cleared)

### Notes
- Install: `pip install "monte-neo @ git+https://github.com/NeoZorK/Monte-Neo.git@v0.0.7"`
- Or: `uv add "monte-neo @ git+https://github.com/NeoZorK/Monte-Neo.git@v0.0.7"`
