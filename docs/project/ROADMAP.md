# Monte-Neo Roadmap (v0.5.0)

## Project rules
- [x] **Silence:** never name external competing products or individuals in this repo
- [x] **ClaimBound Evidence:** only after complete correct private comparisons **and** explicit maintainer permission
- [x] **Version sync:** `_version.py` ↔ CHANGELOG ↔ README ↔ ROADMAP ↔ INDEX ↔ tag ↔ Release ↔ tests ↔ CI
- [x] **Swiss-watch quality:** parity tests, loud failures, perf budgets on 16GB Apple Silicon

## Version 0.5.0 - Venue adapters (Current)
- [x] `BrokerAdapter` intents/reports + paper exchange
- [x] Binance / Bybit adapters (paper default; live env-gated + dry-run)
- [x] Fill reconciliation helper; `.env.example` live flags

## Version 0.4.0 - Tick / L2 paper OMS
- [x] Tick feed + L2 book walk (Python + Numba parity)
- [x] `TickL2Engine` + Metal L2 shader scaffold

## Version 0.3.0 - Paper OMS + accel foundation
- [x] Bar paper OMS + device select + Metal bar-match scaffold

## Next
- [ ] Wire Metal shaders into native bridge (parity vs Numba on M1 Pro 16GB)
- [ ] MC Metal/MLX unify + perf budgets
- [ ] Private P002/P003 (separate harness) — no Evidence without permission
