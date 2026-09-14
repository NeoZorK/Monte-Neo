# Monte-Neo Roadmap (v0.4.0)

## Project rules
- [x] **Silence:** never name external competing products or individuals in this repo
- [x] **ClaimBound Evidence:** only after complete correct private comparisons **and** explicit maintainer permission
- [x] **Version sync:** `_version.py` ↔ CHANGELOG ↔ README ↔ ROADMAP ↔ INDEX ↔ tag ↔ Release ↔ tests ↔ CI
- [x] **Swiss-watch quality:** parity tests, loud failures, perf budgets on 16GB Apple Silicon

## Version 0.4.0 - Tick / L2 paper OMS (Current)
- [x] Tick feed + synthetic OHLC downsample
- [x] L2 book + market/limit walk (Python + Numba parity)
- [x] `TickL2Engine` paper path + Metal L2 shader scaffold
- [x] Stress/perf on large tick streams (16GB-friendly)

## Version 0.3.0 - Paper OMS + accel foundation
- [x] `monte_neo.oms` paper bar OMS (orders, match, portfolio, blotter)
- [x] Device select (`cpu_numba` / `metal` / `mlx` / `auto`)
- [x] Numba batch helper + Metal bar-match shader scaffold

## Version 0.2.0 - Full research bar engine
- [x] Session mask + funding lite + leverage
- [x] Shared-cash portfolio (`run_portfolio_shared_cash`)

## Next
- [ ] v0.5.0 — paper/live exchange adapters (env-gated)
- [ ] MC Metal/MLX unify + parity budgets on M1 Pro 16GB
- [ ] Private P002/P003 (separate harness) — no Evidence without permission
