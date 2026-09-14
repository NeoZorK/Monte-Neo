# Changelog

All notable releases are documented here.
Version source of truth: `src/monte_neo/_version.py`.

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
- License remains **MIT**. Evidence publication still permission-gated.

## [v0.8.0] — 2026-09-14

### Added
- MC Metal/MLX/CPU unified dispatch (`plan_mc_run`) honoring `compute_device` / `use_gpu`
- M1 Pro 16GB-class scenario memory budgets (`plan_scenario_budget`, tile ranges)
- `MCResult.device_used` / `bytes_peak_est` / `accel_plan`; `MCConfig.memory_budget_bytes`
- Docs: `docs/project/mc_accel.md`

### Notes
- Metal-first on Apple Silicon; MLX used when native params are absent but MLX repr exists.
- License remains **MIT**. Evidence publication still permission-gated.

## [v0.7.0] — 2026-09-14

### Added
- Metal L2 book-walk dispatch (PyObjC) with Numba float64 golden parity
- `run_l2_walk` / `run_l2_walk_batch` device-aware paths; TickL2Engine uses them
- Unit parity + performance smoke for Metal L2 batch walk

### Notes
- Metal uses float32; parity tests allow documented rtol/atol vs Numba float64.
- License remains **MIT**. Evidence publication still permission-gated.

## [v0.6.0] — 2026-09-14

### Added
- Metal OMS batch dispatch (PyObjC) with Numba float64 golden parity
- `run_batch_terminal(device=...)` / `preferred_compute_device` for honest device reports
- MCConfig.`compute_device` + engine `compute_pref` checklist
- Perf smoke for auto Metal/Numba batch path

### Notes
- Metal uses float32; parity tests allow documented rtol/atol vs Numba float64.
- License remains **MIT**. Evidence publication still permission-gated.

## [v0.5.0] — 2026-09-14

### Added
- Venue adapters: `PaperExchangeAdapter`, `BinanceAdapter`, `BybitAdapter`
- `make_adapter()` factory + fill reconciliation helper
- Live safety gates: `MONTE_NEO_LIVE_TRADING`, `MONTE_NEO_LIVE_DRY_RUN` (default dry-run)
- `.env.example` keys for Bybit + live flags

### Notes
- Paper mode is default (no network). Live submit without dry-run is blocked in this build.
- License remains **MIT**. Evidence publication still permission-gated.

## [v0.4.0] — 2026-09-14

### Added
- Tick/L2 OMS lane: `TickL2Engine`, synthetic ticks, order book, L2 walk
- Numba `walk_book_market` with Python L2 parity tests
- Metal shader scaffold `oms_l2_walk.metal`
- Docs updated for dual research + OMS tick paths

### Notes
- Paper/synthetic books only in this cut (live adapters later).
- License remains **MIT**. Evidence publication still permission-gated.

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
- No ClaimBound speed evidence until honest top-10 private speed win + user OK.
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
