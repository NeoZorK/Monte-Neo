# Monte-Neo Roadmap (v0.45.0)

Product direction: [PRODUCT_STRATEGY_RU.md](PRODUCT_STRATEGY_RU.md) (verifier for agent-built strategies).

## v0.18.0 — verifier core + agent distribution
- [x] `export_signals()` — bring-your-own positions
- [x] Look-ahead probes (truncation, perturbation, determinism) + AST lint + implausible accuracy
- [x] Deflated Sharpe / PSR with `n_trials`; break-even cost; delay scan; holdout consistency
- [x] `verify_strategy()` → `strategy-verdict/1`; CLI `monte-neo verify`
- [x] Trap Suite v1 (`tests/traps`)
- [x] MCP server `monte-neo-mcp` + Claude Code plugin / Codex / Gemini / Cursor configs
- [x] GitHub Action (`action.yml`)

## v0.19.0 — measured selection bias + agent nudges
- [x] `verify_grid`: in-verifier grid search, measured `n_trials`, anchored walk-forward (`walk_forward_oos`)
- [x] Trap Suite: 9 traps + 3 honest controls + 2 grid strategies + data snooping
- [x] New lint rules (reversed window, full-series rank/stat/fit, group aggregates)
- [x] Claude Code plugin hook (reminder after strategy edits)
- [x] Action: `grid`, PR comment updated in place

## v0.20.0 — reproducible certificates
- [x] `recheck_certificate` / `monte-neo verify --recheck` / MCP `recheck_certificate`
- [x] Grid certificates record `spec` + `folds` (exact reproduction)
- [x] Trap Suite: 11 traps (+ resample aggregate, ML target encoding)
- [x] Lazy `monte_neo` / `monte_neo.core` exports: no MLX load on verifier/CLI/MCP import
- [x] Release workflow (manual dispatch) + tag-driven publish with GitHub Release

## v0.21.0 — Honesty Bench
- [x] `monte-neo bench`: verify agent submissions, compare claims, leaderboard (`honesty-bench/1`)
- [x] Example bench from the Trap Suite + guide

## v0.22.0 — public-run kit
- [x] `monte-neo bench init`: Honesty Bench v1 tasks + hidden answer key; false-discovery / edge-found metrics
- [x] Trap Suite: 17 traps + 5 honest controls; 5 new lint rules

## v0.23.0 — bench protocol
- [x] Trap Suite: 20 traps + 6 honest controls; `last_row` lint rule, `np.*` / `idxmax` full-sample stats
- [x] Honesty Bench run checklist (contamination rules) + leaderboard publication template
- [x] Cleanup candidate list (awaiting approval)

## v0.24.0 — open Trap Suite
- [x] Trap Suite: 25 traps + 9 honest controls; signal-processing lint rules (gradient, centred filters, FFT)
- [x] Trap Suite catalogue + contribution guide + issue form

## v0.25.0 — signed certificates
- [x] Ed25519 signatures: `--keygen`, `--sign`, `--check-signature`; MCP `check_signature`

## v0.26.0 — focus and storefront
- [x] Cleanup: tracked artifacts removed, scripts moved, research lanes frozen, legacy tests isolated
- [x] README / docs home / PyPI metadata rewritten; download badges; banner; CITATION; glama.json
- [x] Marketing plan + launch kit + article draft

## v0.27.0 — signed CI certificates + demo
- [x] GitHub Action: `signing-key`, `upload-certificate`, `key-id` output; self-test covers signing
- [x] Animated README demo from real verifier output

## v0.28.0 — calendar and reversed-series traps
- [x] Trap Suite: 31 traps + 12 honest controls; lint 19 rules (reversed cumulative, reverse count, reindex nearest, group aggregates)

## v0.29.0 — public verification page
- [x] Browser verification of signed certificates (WebCrypto Ed25519), link parameters for badges
- [x] Article published on the docs site

## v0.30.0 — 40 traps
- [x] Trap Suite: 40 traps + 15 honest controls, including two only the dynamic probes catch; lint 20 rules

## v0.31.0 — 50 traps
- [x] Trap Suite: 50 traps + 18 honest controls; lint constant propagation, whole-series methods, np.flip / np.interp, resample aggregates

## v0.32.0 — public bench run tooling
- [x] `bench prepare` / `bench collect` (aliased clean workspaces) + headless runner with transcripts

## v0.32.1 — health fixes
- [x] Release smoke test runs again (in publish.yml) and exercises the product; integration pins raised; MCP server version

## v0.33.0 — data read around the probes
- [x] `external_data` check: strategy code that loads data files or opens network connections is rejected (runtime audit hook + lint rule 21)
- [x] `data_integrity` rejects newest-first, shuffled or duplicated timestamps; CI runs the verifier on Linux, Python 3.11–3.13

## v0.34.0 — audit and polish
- [x] Full audit of the verifier: shorts traded by default in the Python API, certificate records its thresholds, stronger truncation probe, fewer false alarms (lint windows, hit-rate significance)
- [x] Monte Carlo timing test (circular shifts) and grid parameter plateau; 23 honest controls

## v0.35.0 — weights, universes, context, HTML
- [x] Fractional positions (weights) on a target-weight engine equal to the sign engine on unit signals
- [x] Universes (symbol column): cross-sectional probes, survivorship check, equal-weight benchmark, 3 traps + 2 honest controls
- [x] Buy-and-hold benchmark, results by period and market regime, period_consistency check
- [x] Self-contained HTML report (CLI --html / --render, MCP render_report, Action output)

## v0.35.1 — audit fixes
- [x] Broken OHLC bars, MCP error reasons, clear input errors, fast CLI start

## v0.36.0 — data quality, strategy workers, slim install
- [x] data_quality check: one-bar spikes (bad ticks), frozen prices, split jumps, gaps in time, zero volume; bad-tick trap
- [x] Strategy workers: parallel probes (--jobs), time limit per signal() call (--timeout), isolation (--isolate)
- [x] Slim base install (488 MB -> 327 MB): research packages in extras `parquet` and `research`
- [x] verify --precompile; docs for verifying untrusted code in Docker

## v0.36.1 — fixes
- [x] Journal-free engine path (checks of high-turnover strategies 9.8 s -> 0.5 s), numba cache fallback in read-only environments
- [x] Docker image for untrusted code (docker/verify/Dockerfile), release cadence limit removed

## v0.37.0 — security audit, runs without Numba
- [x] Security audit (isolation bypass, certificate key handling, verification page, input limits), SECURITY.md threat model
- [x] Supply chain: Actions pinned by SHA, Bandit + pip-audit + Scorecard workflows, SBOM
- [x] Verifier runs without Numba (identical results), Numba as CPython-only dependency with a `fast` extra

## v0.38.0 — report tear sheet
- [x] HTML report: verdict reason, category cards, log equity + drawdown, rolling Sharpe, monthly heat map, return and timing histograms, cost sensitivity, trade statistics, leak evidence, grid heat map, print stylesheet
- [x] Gallery of example reports; `charts` section in the certificate (not part of the id); docs build checked in CI

## v0.39.0 — professional statistics
- [x] `--claim`: overclaim detection (CLI, MCP, Action, recheck)
- [x] Bootstrap confidence intervals, Minimum Track Record Length, PBO (CSCV) for parameter searches
- [x] Spread estimate from high and low, capacity from volume

## v0.40.0 — Trap Suite 80
- [x] 80 traps and 35 honest controls: ML pipelines, calendar joins, universes, damaged data
- [x] Lint rules `shuffled_split` and `kfold_split` (23 rules)

## v0.41.0 — verification layer for every framework
- [x] Adapters: vectorbt, Freqtrade, Lean, Zipline, plain fills (Backtrader / Nautilus via fills)
- [x] Jupyter display, pandas accessor, `--badge`, pre-commit hook, GHCR image workflow

## v0.42.0 — audience content
- [x] Technical note on the method, weekly "trap of the week" drafts, differences table, false-accusation issue form
- [x] conda-forge recipe draft; owner tasks in `docs/project/STAGE6_OWNER_TASKS_RU.md`

## v0.43.0 — stage 3 leftovers
- [x] Short-borrow and funding fees (CLI, MCP, Action); White Reality Check and Hansen SPA for grids; rolling-window stability

## v0.44.0 — stops for target weights
- [x] SL/TP/trailing stops inside the bar for fractional weights and universes (bit-identical to the discrete engine on unit signals)
- [x] `--sl-pct` / `--tp-pct` / `--trail-pct` in the CLI, MCP and the Action

## v0.45.0 — per-symbol costs
- [x] `--costs-file` / `symbol_costs` / `costs-file`: commission and slippage by symbol, resolved into the certificate

## v0.50.0 — stage 8: arrival time and latency (experimental)
- [x] Quotes with arrival time: `quote_quality` (crossed quotes, negative latency, out-of-order arrivals, bursty latency), bars on the exchange and the arrival clock
- [x] `arrival_lookahead`, `latency_scan` (the delay in ms where the profit vanishes), `latency_monte_carlo` (200 seeded redraws of the observed latency)
- [x] `verify_quotes` / `monte-neo verify --quotes` / MCP `verify_quotes`; `--symbol`, `--order-latency-ms`, `--recheck` for quote certificates
- [x] "Time and latency" section in the HTML report; guide, GIF demo, traps and honest controls
- [x] Quote recorder for Binance futures (`python -m monte_neo.data.quote_recorder`) with the clock-offset uncertainty
- [x] Several feeds in one strategy (`--symbol`, `--feeds`); assumed latency models (`--latency-model`); look-ahead probes on the arrival bars; `spread_cost`; `assumptions` in every certificate
- [x] Checked on 1.18 million real quotes with assumed latency: no false accusation, foresight rejected, a planted edge caught
- [ ] Measure the latency of a machine near the exchange and the false-warning rate among strategies that really earn; then decide which rows may fail the verdict
- Not planned, on purpose: queue position and partial fills (they need the order book and a passive-order model; a rough formula would give false precision)

## v0.49.0 — stage 7: CI in one command
- [x] `monte-neo init-ci`

## v0.48.0 — stage 7: real frameworks
- [x] Adapters for Backtrader, backtesting.py, bt, Nautilus; a CI job runs the real frameworks; close fills read at their own bar (a bug fix)

## v0.47.0 — stage 7: first run and real use
- [x] `verify --demo` (no files) and a plain-language summary under the table
- [x] Adapters checked against real vectorbt, Backtrader, backtesting.py, bt, Nautilus Trader and Zipline (v0.48.0); Freqtrade and Lean adapters still only checked on fake data
- [x] One-line CI setup: `monte-neo init-ci` writes the workflow (v0.49.0)

## v0.46.0 — capacity for universes
- [x] Capacity from volume for multi-symbol universes: pooled fills, tightest symbols listed, "Capacity by symbol" table in the report

## Next (v0.46+)
- [ ] First public bench run (owner runs it; tooling ready in v0.32.0): Claude Code / Codex / Gemini CLI / Cursor → published leaderboard
- [~] Publish to MCP catalogues: official registry (done), glama / smithery / mcp.so / mcpmarket (owner submits; texts in docs/marketing/launch-kit.md)
- [x] Signed certificates (v0.25.0), signing in the GitHub Action (v0.27.0), public verification page (v0.29.0)

## v0.17.7
- [x] Pages homepage: `docs/index.md` at site root; `docs/docs-map.md` replaces `INDEX.md`
- [x] Native index.md site root (sed hack inert); prune old github-pages deployments after ship
- [ ] LocalScorer B — still waiting on real labels

## v0.17.6
- [x] CI PyPI install smoke (`pypi-smoke.yml` + `scripts/verify_pypi_install.sh`)
- [x] SECURITY.md linked from README / CONTRIBUTING / docs INDEX / nav
- [ ] LocalScorer B — still waiting on real labels

## v0.17.5
- [x] Research `device="auto"` prefers cpu_numba for wall clock (`auto_prefer_cpu_numba`)
- [x] Explicit metal/mlx unchanged; OMS `resolve_device` unchanged
- [ ] LocalScorer B — still waiting on real labels

## v0.17.4
- [x] Performance page: M1 Pro 16GB primary table (honest Metal vs cpu_numba wall times)
- [ ] LocalScorer B — still waiting on real labels

## v0.17.3
- [x] Docs trust pack: job-fit scenarios, export-first quickstart, honest performance page
- [x] `scripts/bench_research_bar.py` first-party research-bar timings
- [ ] LocalScorer B — still waiting on real labels

## v0.17.2
- [x] Soften holdout promote gate (`holdout_positive`) + label JSONL log
- [ ] LocalScorer B — still waiting on real labels

## v0.17.1
- [x] Install audit (pipx, TestPyPI recipe, FAQ)
- [x] CONTRIBUTING + issue/PR templates

## v0.17.0
- [x] Holdout / walk-forward helper around export (`holdout_sma_sweep`)
- [ ] LocalScorer B — only if A proves useful
- [x] Install audit / CONTRIBUTING (tier 2) — v0.17.1

## v0.16.0
- [x] Slim default deps + optional extras (`apple` darwin markers, `plot`, `data`, `ml`, `server`, `full`)
- [x] HeuristicPolicy A: ResearchState + triage + CLI `--policy-triage`
- [x] Export UX docs (API + quickstart extras)
- [x] Holdout helper (tier 2) — shipped in v0.17.0
- [ ] LocalScorer B — only if A proves useful

## v0.15.1
- [x] Packaging/CI fixes after v0.15.0 tag (bare install, data wheel, ruff/CI)
- [x] First TestPyPI + PyPI publish (0.15.1)

## v0.15.0
- [x] PyPI-ready packaging prep (`[apple]` extras, metadata, PACKAGING.md)
- [x] Demo screenshots + examples quickstart
- [ ] TestPyPI dry-run + first PyPI publish (maintainer OK)

## v0.14.1
- [x] No-hang Metal/MLX size gate → `cpu_numba` fallback
- [x] README marketing pass + FAQ

## Project rules
- [x] Silence / Evidence permission-gate / version sync / Swiss-watch quality

## Version 0.14.0 - 16GB packing + export depth + positioning (Current)
- [x] `plan_research_bytes` soft budget / tile hints
- [x] Export equity stride + journal + memory block
- [x] README job / non-goals without rival names

## Version 0.13.0 - Research signal factory
- [x] Numba-parallel SMA cross signal grids (`build_sma_cross_grid`)
- [x] Sweep/export split `signal_elapsed_s` / `economics_elapsed_s`
- [x] Unit parity vs single-signal path

## Version 0.12.0 - Research export API + golden vectors
- [x] `monte_neo.backtest.export` stable schema (API v1)
- [x] Frozen golden vectors + `verify_golden_vectors` / `verify_export_golden`
- [x] Timers disclose `includes_signal_build`
- [x] Unit coverage for export schema + Numba golden exactness

## Version 0.11.0 - Metal funding/session/long_short
- [x] Metal research economics: funding + session mask + long_short
- [x] MLX unit skips cleared against current engine API

## Version 0.10.0 - Metal SL/TP/trail research subset
- [x] Metal long/flat batch with SL/TP/trail vs Numba parity
- [x] Funding / session / long_short remain Numba golden

## Version 0.9.0 - Research bar Metal economics
- [x] Metal long/flat batch economics with Numba golden parity
- [x] `device=` on batch / SMA sweep; advanced knobs stay Numba

## Version 0.8.0 - MC Metal/MLX unify + 16GB budgets
- [x] `plan_mc_run` Metal-first / MLX / CPU dispatch
- [x] Scenario memory budgets + tile helpers for M1 Pro 16GB

## Version 0.7.0 - Metal L2 walk dispatch
- [x] PyObjC Metal L2 book-walk with Numba parity

## Version 0.6.0 - Metal OMS batch + compute pref
- [x] PyObjC Metal batch long/flat with Numba parity

## Version 0.5.0 - Venue adapters
- [x] Paper / Binance / Bybit adapters; live env-gated dry-run

## Version 0.4.0 - Tick / L2 paper OMS
- [x] Tick feed + L2 walk + Metal L2 shader scaffold

## Version 0.3.0 - Paper OMS + accel foundation
- [x] Bar OMS + device select + Metal bar-match scaffold

## Next
- [ ] Private P002/P003 (separate harness) — no Evidence without permission
- [ ] Optional OMS hardening (not research speed claim)
- [x] Metal SL/TP/trail research subset
- [x] Release cut when green on main (v0.10.0 / v0.14.0 tagged)
