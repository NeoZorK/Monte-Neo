# Race helpers (Phase-2)

Fast paths for Apple Silicon fair-race:

- `fused_sma_sweep` — Numba parallel float64 SMA grid
- `metal_scenario_batch` — MLX/Metal scenario batch with prefetch overlap

Used by `manifold_bt_comparison` harness. Not a public API contract.
