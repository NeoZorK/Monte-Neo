# Monte-Neo Roadmap (v0.26.0)

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

## Next (v0.27+)
- [ ] First public bench run: same tasks → Claude Code / Codex / Gemini / Cursor → published leaderboard
- [ ] Trap Suite → 50+ traps (now 25 + 9 honest controls; next: survivorship across a universe, timezone edges)
- [~] Publish to MCP catalogues: official registry (done), glama / smithery / mcp.so / mcpmarket (owner submits; texts in docs/marketing/launch-kit.md)
- [~] Signed certificates (v0.25.0) + public verification page; signing in the GitHub Action

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
