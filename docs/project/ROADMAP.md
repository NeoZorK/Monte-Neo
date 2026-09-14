# Monte-Neo Roadmap (v0.6.0)

## Project rules
- [x] Silence / Evidence permission-gate / version sync / Swiss-watch quality

## Version 0.6.0 - Metal OMS batch + compute pref (Current)
- [x] PyObjC Metal batch long/flat with Numba parity
- [x] `run_batch_terminal` / `preferred_compute_device`
- [x] MCConfig.compute_device + engine compute_pref

## Version 0.5.0 - Venue adapters
- [x] Paper / Binance / Bybit adapters; live env-gated dry-run

## Version 0.4.0 - Tick / L2 paper OMS
- [x] Tick feed + L2 walk + Metal L2 shader scaffold

## Version 0.3.0 - Paper OMS + accel foundation
- [x] Bar OMS + device select + Metal bar-match scaffold

## Next
- [ ] Native bridge load of `oms_l2_walk.metal` (parity vs Numba)
- [ ] Deeper MC Metal/MLX scenario unify + 16GB budgets
- [ ] Private P002/P003 (separate harness) — no Evidence without permission
- [ ] Release cut when green on main
