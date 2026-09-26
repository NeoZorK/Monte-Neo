# Changelog

All notable releases are documented here.
Version source of truth: `src/monte_neo/_version.py`.

## [v0.26.0] — 2026-09-26

### Changed
- **README and docs home rewritten** around the verifier: the problem, real CLI output, where to use
  it, why Monte-Neo, quick start for the CLI, agents and the GitHub Action, and certificates
- Badges: PyPI version, total downloads (pepy), downloads per month (pypistats), Python versions, CI,
  license, MCP Registry, supported agents, stars; a "Verified by Monte-Neo" badge for users
- PyPI metadata: new description, keywords and classifiers; author NeoZorK
- New banner `docs/assets/social-preview.png` (README hero, GitHub social preview) and logo mark
  `docs/assets/logo-sphere.png`
- Research lanes frozen (bug fixes only): the indicator generator, the MLX/Metal engine, the paper OMS,
  the policy module and the CLI menu; see "Frozen lanes" in the contributing guide

### Added
- `CITATION.cff`, `glama.json`
- Launch kit and article draft under `docs/marketing/`; internal marketing plan

### Removed
- Tracked build artifacts: `profile_stats.txt`, `exports/`, `verify_gpu_optimizer.py`

### Moved
- `verify_hardware.py` → `scripts/`; one-off Metal/MLX experiments → `scripts/experiments/`;
  `tests/unit/test_coverage_boost*.py` → `tests/unit/legacy_coverage/`

### Notes
- No API change vs 0.25.0.

## [v0.25.0] — 2026-09-26

### Added
- **Signed certificates** (Ed25519, optional extra `monte-neo[sign]`):
  - `monte-neo verify --keygen PREFIX` writes `PREFIX.key` (owner-only) and `PREFIX.pub`;
  - `--sign KEY` adds a `signature` block to the certificate;
  - `--check-signature CERT [--public-key PUB]` checks it (exit code 5 when invalid or signed by another key);
  - library: `sign_certificate`, `check_signature`, `generate_keypair`; result schema `strategy-signature-check/1`
- MCP tool `check_signature`
- `strategy-verdict/1` schema: optional `signature` property (backward compatible)

### Notes
- No breaking API change vs 0.24.0. The default install is unchanged; `cryptography` comes only with
  the `sign` (or `full`) extra.

## [v0.24.0] — 2026-09-26

### Added
- Trap Suite: signal-processing leaks `gradient_leak`, `convolve_same`, `fft_denoise`, whole-sample ranks
  `qcut_full`, `argsort_rank`, plus the honest controls `ewm_cross`, `convolve_causal` and
  `rolling_quantile_band` (25 traps, 9 honest controls)
- Lint rules: `central_difference` (`np.gradient`, fail), `centered_filter` (`convolve` / `correlate` with
  `mode="same"`, `filtfilt`, `sosfiltfilt`, `savgol_filter`, `gaussian_filter1d`, `uniform_filter1d`,
  `medfilt`, fail), `full_sample_transform` (`fft`, `rfft`, `dct`, `hilbert`, `detrend`, warn); `qcut` and
  `argsort` added to `full_sample_rank`
- Guide: [Trap Suite](../guides/trap-suite.md), with the catalogue and how to contribute a trap; a
  "Trap submission" issue form; a test keeps the catalogue in sync with `tests/traps/strategies/`

### Changed
- Lint reports one finding per rule and line (nested calls such as `argsort(argsort(x))` no longer
  produce duplicates)

### Notes
- No breaking API change vs 0.23.0.

## [v0.23.0] — 2026-09-26

### Added
- Trap Suite: `last_row_leak`, `idxmax_leak`, `numpy_global_stat`, plus the honest control
  `cummax_drawdown` (20 traps, 6 honest controls)
- Lint rules: `last_row` (fail) for `.iloc[-k]`, `.values[-k]` and `.to_numpy()[-k]`; `full_sample_stat`
  now also covers `idxmax` / `idxmin` / `argmax` / `argmin` and whole-array `np.mean` / `np.std` / `np.percentile` / …
- Honesty Bench guide: a run checklist (contamination rules for each agent and task) and a leaderboard
  publication template
- Internal: cleanup candidate list with evidence (`docs/project/CLEANUP_CANDIDATES_RU.md`); nothing removed

### Notes
- No breaking API change vs 0.22.0. `np.mean(series)` and similar calls now produce a lint `warn`.

## [v0.22.0] — 2026-09-26

### Added
- **Honesty Bench v1**: `monte-neo bench init <dir>` writes five deterministic tasks (`noise`, `momentum`,
  `mean-reversion`, `costs-trap`, `regime`) with a shared prompt, 5 + 5 bps costs and a hidden
  `answer_key.json`
- Bench metrics from the answer key: **false discovery** (claimed profit on a task with no edge after
  costs) and **edge found** (edge task where the strategy passes verification)
- Trap Suite: `diff_negative`, `pct_change_negative`, `roll_negative`, `merge_asof_forward`,
  `interpolate_leak`, `cumsum_total_norm`, plus the honest controls `resample_shifted` and `expanding_rank`
  (17 traps, 5 honest controls)
- Lint rules: `negative_period` (`diff` / `pct_change`), `negative_roll`, `forward_asof`, `interpolate`
  (fail); `sum` added to `full_sample_stat`

### Fixed
- `test_generator_dynamic` evaluated a random formula on 100 bars. Stacked windows and shifts can need
  about 180 bars of warm-up, so the test now uses 400 bars.

### Notes
- No breaking API change vs 0.21.0.

## [v0.21.0] — 2026-09-26

### Added
- **Agent Backtest Honesty Bench** (`monte_neo.bench`, CLI `monte-neo bench <dir>`). It verifies each
  agent's strategy with the task's costs and the agent's own `n_trials`, compares the claimed return
  with the verified net return, and ranks agents by look-ahead rate, broken submissions, overclaim
  rate and pass rate. Report schema: `honesty-bench/1`, plus a Markdown leaderboard.
- `scripts/make_example_bench.py`: example bench with two illustrative agents built from the Trap Suite
- Guide: [Honesty Bench](../guides/honesty-bench.md)

### Fixed
- MCP Registry publish: `server.json` description shortened to ≤ 100 characters (the registry rejected
  v0.20.0 with 422); `mcp-registry` job stops retrying on validation errors
- `CodeGenerator` no longer emits binary expressions with identical operands (`x / x`, `x - x`), which
  produced constant indicators and made `test_generator_dynamic` flaky

### Notes
- No breaking API change vs 0.20.0.

## [v0.20.0] — 2026-09-26

### Added
- Certificate re-check: `recheck_certificate` / `monte-neo verify --recheck cert.json` (exit 4 when not
  reproduced) / MCP tool `recheck_certificate`. It compares the data, signal and source hashes,
  re-runs the verifier (or the recorded grid search) and compares the verdict and `certificate_id`.
  Schema `strategy-recheck/1`.
- Grid certificates record `grid.spec` and `grid.folds`, so they can be reproduced exactly
- Trap Suite: `resample_max_leak`, `target_encoding_leak` (ML-style target encoding on the full sample)

- `monte-neo mcp` subcommand (same server as `monte-neo-mcp`)
- Official MCP Registry entry `server.json` (`io.github.NeoZorK/monte-neo`) + `mcp-registry` publish job (GitHub OIDC)

### Changed
- `mcp` SDK is now a default dependency, so `uvx monte-neo mcp` works with no extras (`[mcp]` extra kept for compatibility)
- `monte_neo` and `monte_neo.core` export lazily, so `import monte_neo`, the verifier, the MCP server
  and the CLI no longer load MLX / Metal backends (fixes intermittent CI aborts on macOS runners)

### Fixed
- `BinanceDownloader._fetch_klines`: a persistent HTTP 429 / rate limit now raises after
  `MAX_RATE_LIMIT_RETRIES` (5) instead of sleeping forever. This was the cause of CI jobs hanging for an hour.
- `test_misc_one_liners` no longer reaches Binance over the network; CI `test` job has `timeout-minutes: 20`

### Notes
- No breaking API change vs 0.19.0.

## [v0.19.0] — 2026-09-26

### Added
- `verify_grid`: the verifier runs the parameter search itself. It expands the grid (≤ 512 combos),
  measures `n_trials` and the spread of trial Sharpes, verifies the best combo, and runs an anchored
  walk-forward (new `walk_forward_oos` check). Available through CLI `--grid` / `--folds`, the
  MCP tool `verify_grid` and the `grid` input of the Action.
- Static lint rules: `reversed_window` (fail), `full_sample_rank`, `full_sample_stat`,
  `group_aggregate` and `polyfit` fit (warn)
- Trap Suite: `hourly_close_leak`, `reverse_rolling`, `full_polyfit`, `full_rank` traps, the honest
  control `expanding_zscore`, and the grid strategies `sma_params` / `momentum_params`
- Claude Code plugin `PostToolUse` hook: reminds the agent to verify after editing strategy or
  backtest code (once per file per session, never blocks the edit)
- GitHub Action inputs `grid`, `comment` (PR comment updated in place) and `github-token`
- `verify_strategy(extra_checks=, extra=)` extension points; `reproducibility.extra_sha256`

### Changed
- `publish.yml` runs on `v*` tag push: it checks that the tag equals the package version,
  publishes to PyPI, then creates the GitHub Release from this CHANGELOG section

### Notes
- No breaking API change vs 0.18.0.

## [v0.18.0] — 2026-09-26

### Added
- **Strategy verifier** `monte_neo.verify.verify_strategy` → `strategy-verdict/1` certificate
  (verdict, checks, metrics, `next_actions`, SHA-256 reproducibility block, deterministic `certificate_id`)
- Look-ahead probes: truncation, future perturbation (mirrored returns), determinism, AST lint
  (`shift(-k)`, `center=True`, `bfill`, full-sample `fit`, `x[i + k]`), implausible next-bar hit rate
- Cost stress: break-even cost (bps per side), 0/1/2-bar execution delay scan
- Selection-aware statistics: PSR, Deflated Sharpe priced by `n_trials`, sample size, holdout consistency
- `export_signals` — bring-your-own positions through the fee-aware research bar (with signal SHA-256)
- CLI `monte-neo verify` (+ `monte-neo-verify`) with CI exit codes 0/1/2/3 and `--out` certificate
- MCP server `monte-neo-mcp` (`[mcp]` extra; MCP SDK 2.x `MCPServer`, 1.x `FastMCP` fallback):
  `verify_strategy`, `probe_lookahead`, `cost_stress`, `verdict_schema`, `verifier_manifest`
- Agent integrations in `integrations/`: Claude Code plugin (skill `verify-strategy`, `/verify`,
  `.mcp.json`) + root `.claude-plugin/marketplace.json`, Codex, Gemini CLI extension, Cursor rules
- Composite GitHub Action `action.yml` (fails on `REJECT`, step summary, `verdict` output)
- Trap Suite `tests/traps`: 5 lying strategies + 2 honest controls + data-snooping case
- Docs: [Verifier API](../api/verify.md), [Use from agents](../guides/agents.md),
  internal product strategy (`docs/project/PRODUCT_STRATEGY_RU.md`)

### Changed
- README / docs home repositioned: "verify a trading strategy before you trust it"
- CI installs the `mcp` extra and runs `tests/traps`

### Notes
- No breaking change to existing research / export APIs.
- License remains **MIT**. No peer product names in this tree.

## [v0.17.7] — 2026-09-17

### Changed
- Docs site homepage is native MkDocs `docs/index.md` at site root (no `/home/` duplicate)
- Renamed `docs/INDEX.md` → `docs/docs-map.md` (macOS case-insensitive safe next to `index.md`)
- Native MkDocs `docs/index.md` as site root; `docs.yml` checks root index and rejects `site/home/` (sed/copy-home hack removed)
- Maintenance tests and contributing rules point at `docs/docs-map.md`

### Notes
- Docs / Pages infra only — no runtime API break vs 0.17.6.
- License remains **MIT**. No peer product names in this tree.

## [v0.17.6] — 2026-09-17

### Added
- GitHub Actions **PyPI install smoke** (`.github/workflows/pypi-smoke.yml`): `workflow_dispatch`, weekly schedule, and `release` published → clean venv + `pip install monte-neo==… --no-cache-dir` + import policy/holdout (via `scripts/verify_pypi_install.sh`, CDN retries)
- Links to [SECURITY.md](https://github.com/NeoZorK/Monte-Neo/blob/main/SECURITY.md) from README, CONTRIBUTING, docs INDEX, and MkDocs Project nav

### Changed
- `scripts/verify_pypi_install.sh` default version → **0.17.6**; `--no-cache-dir` + retry/sleep for PyPI CDN lag

### Notes
- Docs / OSS trust only — no runtime API break vs 0.17.5.
- License remains **MIT**. No peer product names in this tree.

## [v0.17.5] — 2026-09-17

### Changed
- Research `device="auto"` prefers **`cpu_numba`** for wall clock on typical grids (measured M1 Pro: Metal was ~50–100× slower on 100k×64 / 1M×32)
- Sets `fallback_reason="auto_prefer_cpu_numba"` when auto declines Metal/MLX for speed
- Explicit `device="metal"` / `"mlx"` unchanged (size gate only; may be slow — user's choice)
- OMS `resolve_device("auto")` unchanged (still prefers Metal when available)

### Added
- Env `MONTE_NEO_RESEARCH_AUTO_PREFER_METAL=1` — restore pre-0.17.5 prefer-Metal research auto
- Env `MONTE_NEO_RESEARCH_AUTO_METAL_MIN_COMBOS=N` — allow auto→Metal only when `n_combos >= N`

### Notes
- See [Performance](../development/performance.md) and [FAQ](../guides/FAQ.md).
- License remains **MIT**. No peer product names in this tree.

## [v0.17.4] — 2026-09-17

### Changed
- [Performance](../development/performance.md): primary table is **MacBook Pro M1 Pro 16 GB** real timings (post-warmup)
- Honest guidance: for measured small/medium grids, `cpu_numba` beat Metal wall-clock while `auto` still selected Metal when eligible

### Notes
- Docs / trust only — no runtime API break vs 0.17.3.
- License remains **MIT**. No peer product names in this tree.

## [v0.17.3] — 2026-09-17

### Added
- Job-fit scenarios on [Home](../index.md) and [FAQ](../guides/FAQ.md): when Monte-Neo fits / when not (research bar vs OMS/live; peer-free)
- [Performance](../development/performance.md) rewrite with first-party `export_sma_sweep` timings + `scripts/bench_research_bar.py`
- MkDocs nav: Performance under Get started

### Changed
- [Quick start](../guides/quick-start.md) is **export-first** (pip → export → policy → holdout); CLI wizard moved to optional section
- Softened stale “125x” / “300k ops/sec” / “v0.0.4 targeting” claims in public docs

### Notes
- Docs / trust pack only — no runtime API break vs 0.17.2.
- License remains **MIT**. No peer product names in this tree.

## [v0.17.2] — 2026-09-17

### Changed
- Holdout default **`promote_mode="holdout_positive"`**: positive holdout no longer blocked by large train−holdout gap
- HeuristicPolicy: block promote only when `holdout_promote_ok` is false; high gap → MC flag; holdout can unlock promote

### Added
- `promote_mode="strict"` for legacy conservative gate
- `append_research_label` JSONL logger + CLI `--holdout-log` / `--human-label` (corpus for a future LocalScorer — **not** B yet)

### Notes
- LocalScorer B still deferred until real labeled runs exist.
- License remains **MIT**.

## [v0.17.1] — 2026-09-17

### Added
- CONTRIBUTING + GitHub issue/PR templates
- Install audit docs: pipx, extras matrix, safe TestPyPI `--no-deps` recipe
- FAQ: TestPyPI poison, extras ImportError, policy/holdout CLI pointers

### Changed
- Installation page current release → 0.17.x; docs site link in install/FAQ
- MkDocs nav: Contributing

### Notes
- Docs/OSS friction only — no runtime API break vs 0.17.0.
- License remains **MIT**.

## [v0.17.0] — 2026-09-17

### Added
- **Holdout helper** (`holdout_sma_sweep`, `split_bar_range`): train SMA sweep → score top-K on holdout
  - Schema `mn.holdout_report.v1` with gap / overfit_risk / promote_ok
  - HeuristicPolicy enrichment via `build_research_state(..., holdout_report=)`
  - CLI: `monte-neo --holdout-sma`
- Docs: [Holdout API](../api/holdout.md)

### Notes
- Practical anti-overfit without ML. LocalScorer B still deferred.
- License remains **MIT**. No peer product names in this tree.

## [v0.16.0] — 2026-09-17

### Added
- **HeuristicPolicy A** (`monte_neo.policy`): local deterministic triage after research export
  - `build_research_state` → compact `mn.research_state.v1` (no raw OHLCV)
  - `triage_export` / `HeuristicPolicy.decide` → next_action, promote/MC flags, reasons
  - CLI: `monte-neo --policy-triage path/to/export.json`
- Docs: export API + policy pages; install extras matrix (`[apple]`, `[plot]`, `[data]`, `[ml]`, `[server]`, `[full]`)

### Changed
- **Slim default dependencies** — research-core only (numpy/pandas/pyarrow/numba/rich/CLI)
- Optional extras: `apple` (darwin markers), `plot`, `data`, `ml`, `server`, `full`
- Lazy imports for Binance downloader, websocket client, plot helpers (`monte-neo[data]` / `[plot]`)
- CI syncs `--extra apple --extra plot --extra data --group dev`
- Documentation URL → https://neozork.github.io/Monte-Neo/

### Notes
- Not a cloud “System One” model — offline rules only. Holdout helper / LocalScorer B deferred.
- License remains **MIT**. No peer product names in this tree.

## [v0.15.1] — 2026-09-16

### Fixed
- Bare `pip install` without MLX (`from __future__ import annotations` on acceleration modules)
- Quiet Metal-unavailable import noise (debug level)
- Include `monte_neo.data` in wheels (`.gitignore` `/data/`)
- CI: portable CLI subprocess cwd; ruff clean on coverage boosts
- Coverage close-out for sequential advice + cli `__main__` pragma

### Packaging
- Ready for first TestPyPI / PyPI upload as PEP 440 `0.15.1`
- GitHub tag `v0.15.0` predates these packaging/CI fixes — ship as **0.15.1**

## [v0.15.0] — 2026-09-15

### Fixed
- `verify_export_golden` / `verify_golden_vectors`: auto Metal float32 tolerance band when batch resolves to Metal
- Unit metrics: pin Numba path for deterministic `trade_count`; native extract stub via `_get_native`
- Build: pin `hatchling>=1.24,<1.26` so wheels emit Metadata 2.3 (twine-check friendly)
- Packaging: `.gitignore` `/data/` (root only) so `monte_neo.data` is included in wheels
- Import without MLX: `from __future__ import annotations` on acceleration modules so bare `pip install` works
- Metal extension absence logged at debug (no emoji warning on every import)

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
