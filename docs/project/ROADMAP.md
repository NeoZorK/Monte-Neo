# Monte-Neo Roadmap (v0.3.0)

## Project rules
- [x] **Silence:** never name external competing products or individuals in this repo
- [x] **ClaimBound Evidence:** only after complete correct private comparisons **and** explicit maintainer permission
- [x] **Version sync:** `_version.py` ↔ CHANGELOG ↔ README ↔ ROADMAP ↔ INDEX ↔ tag ↔ Release ↔ tests ↔ CI
- [x] **Swiss-watch quality:** parity tests, loud failures, perf budgets on 16GB Apple Silicon

## Version 0.3.0 - Paper OMS + accel foundation (Current)
- [x] `monte_neo.oms` paper bar OMS (orders, match, portfolio, blotter)
- [x] Device select (`cpu_numba` / `metal` / `mlx` / `auto`)
- [x] Numba batch helper + Metal shader scaffold for OMS bar match
- [x] Unit / integration / stress / perf coverage for OMS lane

## Version 0.2.0 - Full research bar engine
- [x] Session mask + funding lite + leverage
- [x] Shared-cash portfolio (`run_portfolio_shared_cash`)
- [x] Correctness invariants + batch parity with new knobs

## Version 0.1.0 - GP bar engine + public face
- [x] Honest README + logo + badges
- [x] StrategySpec / trail / impact_bps / partial fills
- [x] Fee-aware shared ExecutionModel path

## Next
- [ ] v0.4.0 — tick/L2 matching + MC Metal unify
- [ ] v0.5.0 — paper/live exchange adapters (env-gated)
- [ ] Private P002/P003 protocols (separate harness) — no Evidence without permission
