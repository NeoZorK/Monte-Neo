# Monte-Neo Roadmap (v0.8.0)

## Project rules
- [x] Silence / Evidence permission-gate / version sync / Swiss-watch quality

## Version 0.8.0 - MC Metal/MLX unify + 16GB budgets (Current)
- [x] `plan_mc_run` Metal-first / MLX / CPU dispatch
- [x] Scenario memory budgets + tile helpers for M1 Pro 16GB
- [x] Engine wires `compute_device` / `use_gpu`; result accel fields

## Version 0.7.0 - Metal L2 walk dispatch
- [x] PyObjC Metal L2 book-walk with Numba parity
- [x] `run_l2_walk` / `run_l2_walk_batch` + TickL2Engine wiring

## Version 0.6.0 - Metal OMS batch + compute pref
- [x] PyObjC Metal batch long/flat with Numba parity
- [x] `run_batch_terminal` / `preferred_compute_device`

## Version 0.5.0 - Venue adapters
- [x] Paper / Binance / Bybit adapters; live env-gated dry-run

## Version 0.4.0 - Tick / L2 paper OMS
- [x] Tick feed + L2 walk + Metal L2 shader scaffold

## Version 0.3.0 - Paper OMS + accel foundation
- [x] Bar OMS + device select + Metal bar-match scaffold

## Next
- [ ] Private P002/P003 (separate harness) — no Evidence without permission
- [ ] Research bar Metal economics sweep (Numba golden)
- [ ] Release cut when green on main
