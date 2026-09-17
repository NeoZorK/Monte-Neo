# Monte-Neo Roadmap (v0.17.4)

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
